"""Annotate stress results with the internal (instructor) retries of each request.

Instructor re-asks the main LLM call up to 6 times when the output fails the
``EstimationResult`` validator and returns the usage SUMMED over attempts, so
``tokens_in`` / ``tokens_out`` / ``cost_usd`` in ``results.csv`` are inflated on
turns with internal retries. This script post-processes the CSV with the
exported server log and appends estimate columns. Existing columns are never
modified.

Usage::

    uv run python -m evals.stress.annotate_attempts \
        --csv evals/stress/results.csv --log evals/stress/server.log
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import os
import re
import statistics
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.llm_wrapper import _estimate_cost

MAX_ATTEMPTS = 6
COST_MODEL = "gpt-4o-mini"
# Score weights (context term, output term); chosen against the log_anchored rows.
W_B = 0.5
W_O = 1.0

NEW_COLUMNS = [
    "internal_attempts_est",
    "tokens_in_first_attempt_est",
    "attempts_method",
    "tokens_in_log",
    "tokens_out_log",
    "cost_usd_log",
]

_USAGE_RE = re.compile(r"completion_tokens=(\d+), prompt_tokens=(\d+)")
_RECEIVED_RE = re.compile(r"session_estimate_received\b.*?\bsession_id=(\S+)")
_COMPLETED_RE = re.compile(r"llm_structured_chat_completed\b.*?\btokens_in=(\d+) tokens_out=(\d+)")


@dataclass(frozen=True)
class FailedRequest:
    """Cumulative usage of each attempt inside one failed instructor call."""

    prompt_cum: list[int]
    completion_cum: list[int]

    @property
    def n_attempts(self) -> int:
        return len(self.prompt_cum)

    @property
    def first_prompt(self) -> int:
        return self.prompt_cum[0]

    @property
    def tokens_in(self) -> int:
        return self.prompt_cum[-1]

    @property
    def tokens_out(self) -> int:
        return self.completion_cum[-1]


@dataclass(frozen=True)
class Request:
    """One ``POST /estimate`` as seen in the server log."""

    session_id: str
    failed: FailedRequest | None
    tokens_in: int | None
    tokens_out: int | None


def parse_failed_line(line: str) -> FailedRequest:
    pairs = _USAGE_RE.findall(line)
    if not pairs:
        raise ValueError("no usage found in failed line")
    return FailedRequest(
        prompt_cum=[int(p) for _, p in pairs],
        completion_cum=[int(c) for c, _ in pairs],
    )


def parse_log(lines: list[str]) -> list[Request]:
    """Split the log into requests; the first outcome line after the start wins."""
    requests: list[Request] = []
    sid: str | None = None
    for line in lines:
        m = _RECEIVED_RE.search(line)
        if m:
            if sid is not None:
                raise AssertionError(f"request of session {sid} has no outcome line")
            sid = m.group(1)
            continue
        if sid is None:
            continue
        if "llm_structured_chat_failed" in line:
            requests.append(Request(sid, parse_failed_line(line), None, None))
            sid = None
            continue
        c = _COMPLETED_RE.search(line)
        if c:
            requests.append(Request(sid, None, int(c.group(1)), int(c.group(2))))
            sid = None
    if sid is not None:
        raise AssertionError(f"request of session {sid} has no outcome line")
    return requests


def cumulative_input(n: int, b: float, o: float, alpha: float, beta: float) -> float:
    """Summed prompt tokens over ``n`` attempts (model calibrated on failed calls)."""
    return n * b + alpha * o * n * (n - 1) / 2 + beta * o * n * (n - 1) * (n - 2) / 6


def estimate_calibration(failed: list[FailedRequest]) -> tuple[float, float]:
    """Median alpha, beta from failed requests (needs >= 3 attempts each)."""
    alphas: list[float] = []
    betas: list[float] = []
    for f in failed:
        if f.n_attempts < 3:
            continue
        p = f.prompt_cum
        a1, a2, a3 = p[0], p[1] - p[0], p[2] - p[1]
        o = f.tokens_out / f.n_attempts
        if o <= 0:
            continue
        alphas.append((a2 - a1) / o)
        betas.append(((a3 - a1) - 2 * (a2 - a1)) / o)
    return statistics.median(alphas), statistics.median(betas)


def first_attempt_given_n(
    tokens_in: float, tokens_out: float, n: int, alpha: float, beta: float
) -> float | None:
    """First-attempt prompt tokens if the request ran ``n`` attempts; None if impossible."""
    o = tokens_out / n
    b = (tokens_in - alpha * o * n * (n - 1) / 2 - beta * o * n * (n - 1) * (n - 2) / 6) / n
    return b if b > 0 else None


def choose_n_anchored(tokens_in: float, tokens_out: float, b: float, alpha: float, beta: float) -> int:
    """n in 1..6 whose predicted cumulative input is closest to the observed one."""
    best_n, best_err = 1, math.inf
    for n in range(1, MAX_ATTEMPTS + 1):
        err = abs(cumulative_input(n, b, tokens_out / n, alpha, beta) - tokens_in)
        if err < best_err:
            best_n, best_err = n, err
    return best_n


def choose_n_estimated(
    tokens_in: float,
    tokens_out: float,
    b_ref: float | None,
    o_ref: float,
    alpha: float,
    beta: float,
    w_b: float = W_B,
    w_o: float = W_O,
) -> tuple[int, float]:
    """n minimising a log-distance to the context (b_ref) and output (o_ref) references."""
    if b_ref is None:
        return 1, float(tokens_in)
    best: tuple[int, float] | None = None
    best_score = math.inf
    for n in range(1, MAX_ATTEMPTS + 1):
        b_n = first_attempt_given_n(tokens_in, tokens_out, n, alpha, beta)
        if b_n is None or tokens_out <= 0:
            continue
        score = w_b * abs(math.log(b_n / b_ref)) + w_o * abs(math.log((tokens_out / n) / o_ref))
        if score < best_score:
            best, best_score = (n, b_n), score
    return best if best is not None else (1, float(tokens_in))


def _unit_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (row["source"], row["scenario"], row["attachment_size_kb"], row["repeat"])


def map_rows_to_requests(rows: list[dict[str, str]], requests: list[Request]) -> list[Request]:
    """Align every CSV row with its log request. Raises AssertionError on any mismatch.

    A run unit (source, scenario, size, repeat) is one session. Units with ok rows
    know their session id; units made only of error rows (aborted sessions) take the
    unclaimed all-failed log sessions in log order.
    """
    by_sid: dict[str, list[Request]] = collections.OrderedDict()
    for r in requests:
        by_sid.setdefault(r.session_id, []).append(r)

    units: dict[tuple[str, str, str, str], list[int]] = collections.OrderedDict()
    for i, row in enumerate(rows):
        units.setdefault(_unit_key(row), []).append(i)

    unit_sid: dict[tuple[str, str, str, str], str | None] = {}
    for key, idxs in units.items():
        sids = {rows[i]["session_id"] for i in idxs if rows[i]["session_id"]}
        assert len(sids) <= 1, f"unit {key} spans several sessions: {sids}"
        unit_sid[key] = next(iter(sids), None)
    claimed = {s for s in unit_sid.values() if s}
    assert len(claimed) == sum(1 for s in unit_sid.values() if s), "session shared by units"

    orphan_pool = [
        sid
        for sid, reqs in by_sid.items()
        if sid not in claimed and all(q.failed is not None for q in reqs)
    ]
    for key, idxs in units.items():
        if unit_sid[key] is not None:
            continue
        candidates = [s for s in orphan_pool if len(by_sid[s]) == len(idxs)]
        assert candidates, f"no all-failed log session with {len(idxs)} requests for unit {key}"
        unit_sid[key] = candidates[0]
        orphan_pool.remove(candidates[0])

    aligned: list[Request | None] = [None] * len(rows)
    for key, idxs in units.items():
        sid = unit_sid[key]
        assert sid in by_sid, f"session {sid} of unit {key} not found in the log"
        reqs = by_sid[sid]
        assert len(reqs) == len(idxs), (
            f"session {sid}: {len(reqs)} log requests vs {len(idxs)} CSV rows"
        )
        for i, req in zip(idxs, reqs):
            row = rows[i]
            if row["error"]:
                assert req.failed is not None, f"session {sid} row {i}: CSV error, log completed"
            else:
                assert req.failed is None, f"session {sid} row {i}: CSV ok, log failed"
                assert str(req.tokens_in) == row["tokens_in"], (
                    f"session {sid} row {i}: tokens_in {row['tokens_in']} != log {req.tokens_in}"
                )
            aligned[i] = req
    return [a for a in aligned if a is not None]


def _per_attempt_output(failed: list[FailedRequest]) -> float:
    return statistics.median(f.tokens_out / f.n_attempts for f in failed)


def annotate_rows(
    rows: list[dict[str, str]],
    requests: list[Request],
    alpha: float,
    beta: float,
    o_ref: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Add the estimate columns. ``requests[i]`` is the log request of ``rows[i]``.

    ``o_ref`` (median per-attempt output of failed requests) defaults to the median
    over all failed requests in ``requests``.
    """
    assert len(rows) == len(requests)
    all_failed = [r.failed for r in requests if r.failed is not None]
    if o_ref is None:
        o_ref = _per_attempt_output(all_failed)
    out: list[dict[str, Any]] = []
    sess: list[str] = []
    turns: list[int] = []
    last_ok_turn: dict[str, int] = {}
    anchor_b: dict[int, float] = {}
    last_failed_b: dict[tuple[str, int], float] = {}
    for i, (row, req) in enumerate(zip(rows, requests)):
        sid = req.session_id
        sess.append(sid)
        if row["error"]:
            assert req.failed is not None, f"row {i}: CSV error but log request completed"
            turn = last_ok_turn.get(sid, 0) + 1
            last_failed_b[(sid, turn)] = float(req.failed.first_prompt)
        else:
            assert req.failed is None, f"row {i}: CSV ok but log request failed"
            assert str(req.tokens_in) == row["tokens_in"], f"row {i}: tokens_in differs from log"
            turn = int(row["turn_index"])
            last_ok_turn[sid] = turn
            if (sid, turn) in last_failed_b:
                anchor_b[i] = last_failed_b[(sid, turn)]
        turns.append(turn)

    valid = [i for i, r in enumerate(rows) if not r["error"]]

    def b_ref_for(i: int) -> float | None:
        others = [j for j in valid if sess[j] == sess[i] and j != i]
        near = [float(rows[j]["tokens_in"]) for j in others if abs(turns[j] - turns[i]) <= 2]
        if near:
            return min(near)
        far = [float(rows[j]["tokens_in"]) for j in others]
        return min(far) if far else None

    def o_ref_without(sid: str) -> float:
        rest = [r.failed for r in requests if r.failed is not None and r.session_id != sid]
        return _per_attempt_output(rest) if rest else o_ref

    counts: collections.Counter[str] = collections.Counter()
    attempts_dist: collections.Counter[int] = collections.Counter()
    disagreements: list[dict[str, Any]] = []
    agree = total = agree_out = 0
    out_only_disagreements: list[dict[str, Any]] = []
    cost_sum = 0.0
    for i, (row, req) in enumerate(zip(rows, requests)):
        new = dict(row)
        if row["error"]:
            f = req.failed
            assert f is not None
            new.update(
                internal_attempts_est=f.n_attempts,
                tokens_in_first_attempt_est=f.first_prompt,
                attempts_method="log",
                tokens_in_log=f.tokens_in,
                tokens_out_log=f.tokens_out,
                cost_usd_log=_estimate_cost(COST_MODEL, f.tokens_in, f.tokens_out),
            )
            cost_sum += float(new["cost_usd_log"])
        else:
            tin, tout = float(row["tokens_in"]), float(row["tokens_out"])
            b_ref = b_ref_for(i)
            if i in anchor_b:
                b = anchor_b[i]
                n = choose_n_anchored(tin, tout, b, alpha, beta)
                method = "log_anchored"
                total += 1
                o_loo = o_ref_without(sess[i])
                n_h, b_h = choose_n_estimated(tin, tout, b_ref, o_loo, alpha, beta)
                n_o, _ = choose_n_estimated(tin, tout, b_ref, o_loo, alpha, beta, w_b=0.0)
                detail = {
                    "session": sess[i],
                    "turn": turns[i],
                    "anchored_n": n,
                    "tokens_in": int(tin),
                    "tokens_out": int(tout),
                    "b_anchor": round(b),
                }
                if n_h == n:
                    agree += 1
                else:
                    disagreements.append({**detail, "estimated_n": n_h, "b_estimated": round(b_h)})
                if n_o == n:
                    agree_out += 1
                else:
                    out_only_disagreements.append({**detail, "out_only_n": n_o})
            else:
                n, b = choose_n_estimated(tin, tout, b_ref, o_ref, alpha, beta)
                method = "estimated"
            new.update(
                internal_attempts_est=n,
                tokens_in_first_attempt_est=round(b),
                attempts_method=method,
                tokens_in_log="",
                tokens_out_log="",
                cost_usd_log="",
            )
        counts[new["attempts_method"]] += 1
        attempts_dist[int(new["internal_attempts_est"])] += 1
        out.append(new)

    info = {
        "o_ref": o_ref,
        "method_counts": dict(counts),
        "attempts_dist": dict(sorted(attempts_dist.items())),
        "agreement": {"total": total, "agree": agree, "disagreements": disagreements},
        "agreement_out_only": {
            "total": total,
            "agree": agree_out,
            "disagreements": out_only_disagreements,
        },
        "error_cost_sum": round(cost_sum, 6),
    }
    return out, info


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames is not None
        return list(reader.fieldnames), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def _print_summary(alpha: float, beta: float, n_alpha: int, info: dict[str, Any]) -> None:
    print(f"alpha median = {alpha:.4f}, beta median = {beta:.4f} (from {n_alpha} failed requests)")
    print(f"rows per method: {info['method_counts']}")
    print(f"internal_attempts_est distribution: {info['attempts_dist']}")
    print(f"o_ref (median per-attempt output over all failed requests) = {info['o_ref']:.1f}")
    for label, key in (
        ("hybrid (leave-session-out o_ref)", "agreement"),
        ("out-only (weight 0 on b)", "agreement_out_only"),
    ):
        ag = info[key]
        print(f"log_anchored agreement on n, {label}: {ag['agree']}/{ag['total']}")
        for d in ag["disagreements"]:
            print(f"  disagreement: {d}")
    print(f"sum of cost_usd_log over error rows: {info['error_cost_sum']:.6f} USD")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", type=Path, default=Path("evals/stress/results.csv"))
    ap.add_argument("--log", type=Path, default=Path("evals/stress/server.log"))
    args = ap.parse_args(argv)

    fieldnames, rows = _read_csv(args.csv)
    base_fields = [c for c in fieldnames if c not in NEW_COLUMNS]
    rows = [{k: r[k] for k in base_fields} for r in rows]
    requests = parse_log(args.log.read_text(encoding="utf-8").split("\n"))
    failed = [r.failed for r in requests if r.failed is not None]
    alpha, beta = estimate_calibration(failed)

    aligned = map_rows_to_requests(rows, requests)
    out, info = annotate_rows(rows, aligned, alpha, beta)
    _print_summary(alpha, beta, len(failed), info)

    fd, tmp_name = tempfile.mkstemp(suffix=".csv", dir=args.csv.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        _write_csv(tmp, base_fields + NEW_COLUMNS, out)
        new_fields, new_rows = _read_csv(tmp)
        assert new_fields[: len(base_fields)] == base_fields, "original columns changed"
        assert len(new_rows) == len(rows)
        for a, b in zip(rows, new_rows):
            assert all(a[c] == b[c] for c in base_fields), "original values changed"
        tmp.replace(args.csv)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"wrote {len(out)} rows to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
