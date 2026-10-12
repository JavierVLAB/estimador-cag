"""Unit tests for the internal-retry annotator (synthetic data only)."""

from __future__ import annotations

import pytest

from evals.stress.annotate_attempts import (
    Request,
    annotate_rows,
    choose_n_anchored,
    choose_n_estimated,
    cumulative_input,
    estimate_calibration,
    first_attempt_given_n,
    parse_failed_line,
    parse_log,
)


def _failed_line(prompts: list[int], completions: list[int]) -> str:
    gens = "".join(
        f"usage=Usage(completion_tokens={c}, prompt_tokens={p}, total_tokens={p + c}, x=1)"
        for p, c in zip(prompts, completions)
    )
    return (
        "estimator  | 2026-10-11T16:01:03.130904Z [error    ] llm_structured_chat_failed     "
        f"error='<failed_attempts> {gens} </failed_attempts>' error_type=InstructorRetryException"
    )


def test_parse_failed_line_reads_cumulative_usage_per_attempt() -> None:
    line = _failed_line([100, 250, 450], [10, 20, 30])
    parsed = parse_failed_line(line)
    assert parsed.prompt_cum == [100, 250, 450]
    assert parsed.completion_cum == [10, 20, 30]
    assert parsed.n_attempts == 3
    assert parsed.first_prompt == 100
    assert parsed.tokens_in == 450
    assert parsed.tokens_out == 30


def test_cumulative_input_matches_per_attempt_model() -> None:
    b, o, alpha, beta = 1000.0, 100.0, 3.5, 2.0
    n = 5
    expected = sum(
        b + (k - 1) * alpha * o + (k - 1) * (k - 2) / 2 * beta * o for k in range(1, n + 1)
    )
    assert cumulative_input(n, b, o, alpha, beta) == pytest.approx(expected)
    assert cumulative_input(1, b, o, alpha, beta) == pytest.approx(b)


def test_estimate_calibration_recovers_alpha_beta_as_medians() -> None:
    alpha, beta, b, o = 3.0, 2.0, 1000, 100
    per_attempt = [b + (k - 1) * alpha * o + (k - 1) * (k - 2) / 2 * beta * o for k in range(1, 7)]
    prompts, acc = [], 0.0
    for a in per_attempt:
        acc += a
        prompts.append(round(acc))
    completions = [o * k for k in range(1, 7)]
    failed = [parse_failed_line(_failed_line(prompts, completions))] * 3
    a_hat, b_hat = estimate_calibration(failed)
    assert a_hat == pytest.approx(alpha, rel=1e-6)
    assert b_hat == pytest.approx(beta, rel=1e-6)


def test_first_attempt_given_n_inverts_cumulative_input() -> None:
    alpha, beta = 3.5, 2.0
    n, b, o = 4, 2000.0, 120.0
    tokens_in = cumulative_input(n, b, o, alpha, beta)
    got = first_attempt_given_n(tokens_in, o * n, n, alpha, beta)
    assert got == pytest.approx(b)


def test_first_attempt_given_n_discards_non_positive() -> None:
    assert first_attempt_given_n(100, 5000, 6, 3.5, 2.0) is None


def test_choose_n_anchored_picks_n_closest_to_observed_total() -> None:
    alpha, beta, b = 3.5, 2.0, 3000.0
    for true_n in (1, 2, 3, 4, 6):
        o = 150.0
        tokens_in = round(cumulative_input(true_n, b, o, alpha, beta))
        assert choose_n_anchored(tokens_in, round(o * true_n), b, alpha, beta) == true_n


def test_choose_n_estimated_picks_n_matching_both_references() -> None:
    alpha, beta, b = 3.5, 2.0, 3000.0
    o = 150.0
    tokens_in = round(cumulative_input(3, b, o, alpha, beta))
    n, b_est = choose_n_estimated(tokens_in, round(o * 3), 3000.0, o, alpha, beta)
    assert n == 3
    assert b_est == pytest.approx(b, rel=0.01)


def test_choose_n_estimated_output_weight_breaks_context_ambiguity() -> None:
    alpha, beta = 3.5, 2.0
    # Same tokens_in, but a wildly wrong b_ref: only the output reference can tell n.
    o = 150.0
    tokens_in = round(cumulative_input(4, 3000.0, o, alpha, beta))
    n, _ = choose_n_estimated(tokens_in, round(o * 4), 100000.0, o, alpha, beta, w_b=0.0)
    assert n == 4


def test_choose_n_estimated_falls_back_to_single_attempt_without_b_ref() -> None:
    assert choose_n_estimated(100, 50, None, 300.0, 3.5, 2.0) == (1, 100.0)


def test_choose_n_estimated_skips_non_positive_b() -> None:
    n, b = choose_n_estimated(100, 5000, 100.0, 300.0, 3.5, 2.0)
    assert n < 6 and b > 0


def test_parse_log_splits_requests_and_takes_first_outcome_line() -> None:
    sid = "11111111-1111-1111-1111-111111111111"
    lines = [
        f"estimator  | t [info     ] session_estimate_received      session_id={sid} x=1",
        "estimator  | t [info     ] llm_structured_chat_completed  cost_usd=0.1 tokens_in=500 tokens_out=50",
        "estimator  | t [info     ] llm_structured_chat_completed  cost_usd=0.1 tokens_in=9 tokens_out=9",
        f"estimator  | t [info     ] session_estimate_received      session_id={sid} x=1",
        _failed_line([100, 250], [10, 20]),
    ]
    reqs = parse_log(lines)
    assert [r.session_id for r in reqs] == [sid, sid]
    assert reqs[0].failed is None and (reqs[0].tokens_in, reqs[0].tokens_out) == (500, 50)
    assert reqs[1].failed is not None and reqs[1].failed.n_attempts == 2


def _row(sid: str, turn: int, tin: int, tout: int, error: bool = False, unit: str = "u") -> dict:
    return {
        "source": "main",
        "scenario": unit,
        "attachment_size_kb": "0",
        "repeat": "0",
        "turn_index": "" if error else str(turn),
        "attempt": "1",
        "session_id": "" if error else sid,
        "tokens_in": "" if error else str(tin),
        "tokens_out": "" if error else str(tout),
        "error": "boom" if error else "",
    }


def test_annotate_rows_maps_requests_and_labels_methods() -> None:
    alpha, beta = 3.5, 2.0
    sid = "s1"
    b = 2000.0
    o = 100.0

    def ok(n: int) -> tuple[int, int]:
        return round(cumulative_input(n, b, o, alpha, beta)), round(o * n)

    failed_prompts, acc = [], 0.0
    for k in range(1, 7):
        acc += b + (k - 1) * alpha * o + (k - 1) * (k - 2) / 2 * beta * o
        failed_prompts.append(round(acc))
    failed = parse_failed_line(_failed_line(failed_prompts, [100 * k for k in range(1, 7)]))
    t1_in, t1_out = ok(1)
    t2_in, t2_out = ok(1)
    t3_in, t3_out = ok(2)
    t4_in, t4_out = ok(1)
    rows = [
        _row(sid, 1, t1_in, t1_out),
        _row(sid, 2, t2_in, t2_out),
        _row(sid, 0, 0, 0, error=True),
        _row(sid, 3, t3_in, t3_out),
        _row(sid, 4, t4_in, t4_out),
    ]
    requests = [
        Request(sid, None, t1_in, t1_out),
        Request(sid, None, t2_in, t2_out),
        Request(sid, failed, None, None),
        Request(sid, None, t3_in, t3_out),
        Request(sid, None, t4_in, t4_out),
    ]
    out, info = annotate_rows(rows, requests, alpha, beta)
    assert [r["attempts_method"] for r in out] == [
        "estimated",
        "estimated",
        "log",
        "log_anchored",
        "estimated",
    ]
    assert out[2]["internal_attempts_est"] == 6
    assert out[2]["tokens_in_log"] == failed_prompts[-1]
    assert out[2]["tokens_in_first_attempt_est"] == failed_prompts[0]
    assert out[3]["internal_attempts_est"] == 2
    assert out[3]["tokens_in_first_attempt_est"] == failed_prompts[0]
    assert out[0]["tokens_in_log"] == ""
    assert out[0]["internal_attempts_est"] == 1
    assert info["agreement"]["total"] == 1
    assert info["agreement"]["agree"] == 1
    assert info["agreement_out_only"]["total"] == 1


def test_annotate_rows_fails_loudly_on_outcome_mismatch() -> None:
    rows = [_row("s1", 1, 500, 50)]
    requests = [Request("s1", parse_failed_line(_failed_line([100, 250], [10, 20])), None, None)]
    with pytest.raises(AssertionError):
        annotate_rows(rows, requests, 3.5, 2.0)
