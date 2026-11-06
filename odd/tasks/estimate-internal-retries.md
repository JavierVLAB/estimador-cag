# estimate-internal-retries

## Objective

Add columns to `evals/stress/results.csv` that separate the real per-attempt context of each turn from the summed usage instructor reports, without changing any existing column.

## Problem

Instructor re-asks the LLM (up to 6 times) when the output fails the `EstimationResult` validator. The `usage` it returns is the sum over all attempts (`update_total_usage`, `instructor/core/retry.py`), so `tokens_in`/`cost_usd` on a turn with internal retries are 2–4× the real context. The runner's `attempt` column only counts whole-request retries (502s), not these internal ones. Evidence: growing 100 KB, steady $0.0120/turn; turn 8 `ok attempt=1` costs $0.0240 (×2), turn 10 `ok attempt=2` costs $0.0364 (×3).

Also, the 76 error rows record `cost_usd = 0`, although each failed request ran 6 attempts.

## Data available

- `evals/stress/server.log` (exported from `docker compose logs estimator`, ANSI stripped). Each `llm_structured_chat_failed` line holds the 6 attempts with cumulative `prompt_tokens`/`completion_tokens`. Each request starts with `session_estimate_received session_id=...`; requests are sequential.
- Calibration from the 76 failed requests: per-attempt input `a_k = b + (k-1)·α·o + (k-1)(k-2)/2·β·o`, where `b` is the first-attempt input and `o` the mean output per attempt. Median α = 3.58 (2.85–3.88), β = 2.13 (1.61–2.33).

## Scope and constraints

- Existing columns and values stay byte-identical. Only new columns are appended.
- Post-processing only: no LLM calls, no CAG changes, no dependency changes.
- Backup of the pre-change CSV: session scratchpad `results_before_annotate.csv` (sha1 `b98c017a53801b9264d03da2a967dd27e93a3c29`).

## TDD

- Mode: strict, enabled. Source: global user configuration.
- Runner: `uv run pytest`.

## Tasks

- [x] T1 — `evals/stress/annotate_attempts.py` + `tests/test_annotate_attempts.py`: parse the log, map failed requests to CSV error rows, estimate internal attempts and first-attempt tokens for valid rows, append columns, print a validation summary. Route: delegated writer (writer trigger: script + tests).
- [x] T2 — Independent read-only verification of the computed values (user request). Route: delegated verifier.
- [x] T3 — Update `evals/stress/REPORT.md` (2a, 2b, totals, claims, limitations) with the corrected values. Route: inline (1 file).

## Acceptance criteria

- Original columns identical to the backup.
- Error rows: `internal_attempts_est` and log tokens/cost taken exactly from the log.
- Validation summary reports how often the neighbour method agrees with the log-anchored method.
- Full suite `uv run pytest` green.

## Progress

- 2026-10-12: log exported, calibration measured, backup taken.
- 2026-10-12: T1 by delegated writer (strict TDD). RED: ImportError at collection; GREEN: `uv run pytest -q` 197 passed. First 30 columns identical to backup (339 lines). All 338 rows mapped to log requests; 5 all-error sessions matched in log order (assumption).
  - First estimator (median of neighbours' tokens_in) agreed with log_anchored rows on 29/43: neighbours are themselves inflated. Replaced by hybrid `estimated`: score = 0.5·|ln(b_n/b_ref)| + |ln(o_n/o_ref)|, b_ref = min tokens_in of same-session turns within ±2, o_ref = median per-attempt output over failed requests (304.8). Agreement 41/43 (leave-session-out o_ref); out-only variant 36/43. Weights chosen against the anchored rows (tuning risk, disclosed).
  - Methods: estimated 219, log 76, log_anchored 43. Attempts distribution {1:159, 2:61, 3:19, 4:14, 5:8, 6:77}. Error rows real cost from log: $1.228791.
  - Finding: growing 0 KB "steady" ~11K-token turns are 2 attempts of ~5K, not 1.

- 2026-10-12: T2 independent verifier (did not read the script): all 7 items CONFIRMED — 30 original columns identical, mapping 338/338, log rows exact, alpha/beta/o_ref, 43 anchored + 219 estimated rows match, distribution identical, 41/43 agreement. 5 all-error sessions matched by log order flagged as assumption.
- 2026-10-12: T3 inline. REPORT.md updated: spend line, retries table in section 1, retries section + 2a rebuilt on single-attempt turns and real context, latency by attempts, one-attempt cost table in 2b, paragraphs 1-2, claims 2-4, limitations, reproducibility. Key numbers: 39% of valid turns re-asked; failed requests $1.229 > valid $0.999; retries ≈71% of $2.24; +~3 s per extra attempt; single-attempt P50 ~3 s up to 40K context.

## Next step

Javi reviews REPORT.md.
