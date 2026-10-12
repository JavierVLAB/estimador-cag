# fix-turn-observation

## Objective

Make the per-turn `TurnObservation` carry real data so the stress-test CSV can produce the cost and recall-vs-N curves.

## Problem

Smoke run on 2026-10-11 (growing, 0 KB, 1 repeat, 20 turns):

1. `tokens_in`, `tokens_out`, `cost_usd` are 0 on every turn. `LLMWrapper.complete_structured_chat` (`app/services/llm_wrapper.py:236-248`) returns meta with only `model`, `provider`, `latency_ms`.
2. `turn_index` plateaus at 7 from turn 7 on. `app/services/estimation.py:259` derives it from `len(history.messages) // 2`, but the window was already trimmed to `MAX_CONVERSATION_TURNS=6` by the previous turn's compression.

## Scope and constraints

- Fix only these two bugs. Do not change CAG constants, prompts, compression, or retries (exercise forbids optimising the CAG).
- Token/cost fields report the main estimation call only (same call whose latency is already reported). Summarizer and metadata-extractor calls are not added in.
- No dependency changes. No `.env` access. No real LLM calls in tests.

## TDD

- Mode: strict, enabled. Source: global user configuration ("Strict TDD Mode: enabled").
- Runner: `uv run pytest`.

## Tasks

- [x] T1 — `complete_structured_chat` returns `tokens_in`, `tokens_out`, `cost_usd` in meta, using the provider usage and the existing `MODEL_COSTS` pricing. Route: delegated (writer trigger, 2+ non-trivial files across T1+T2).
- [x] T2 — `turn_index` counts every turn the session has seen, independent of the sliding window. Route: delegated (same writer).
- [x] T3 — Stress runner retries a failed turn (default 2 extra attempts, CLI flag) instead of aborting the session at the first error; every failed attempt still writes an error row. Only aborts after the last attempt fails. Reason: 2 of 2 smoke re-runs died at turn 1 (LLM phases-sum validation, 6 instructor retries) and the abort left empty sessions. A failed turn is never appended to history, so retrying the same turn keeps the conversation intact. Runner only; CAG untouched. Route: delegated (runner + test).

- [x] T4 — Runner measures more than the turn-1 fact. (a) Full fact tracker: per row, how many facts introduced in earlier turns are still found (`facts_tracked`, `facts_recalled`, `fact_recall`). (b) Competing facts for pivot (React Native vs Flutter) and contradiction (30000 vs 80000 EUR): per row, where the old and the new value appear (summary / anchors / metadata). `memory_drift_passed` (turn-1 fact) unchanged. Reason: exercise block 2 asks whether the pivot/contradiction is absorbed and which value is kept, promoted to anchor, or summarised; the runner only tracked the turn-1 project name and the CSV keeps no metadata. Budget facts "30"/"80" are too loose as substrings. Route: delegated (scenarios + runner + tests).
- [x] T5 — `GET /sessions/{id}` exposes `summary` text and `anchors` (anchor message contents) so `MemoryDriftMetric` and the location columns can search them, as the metric docstring and exercise block 4 assume. Route: inline (1 app file + 1 test).

## Acceptance criteria

- Unit tests cover both bugs (RED observed before the fix, GREEN after).
- Full suite `uv run pytest` green.
- A re-run of the smoke test after Javi rebuilds the container shows non-zero tokens/cost and `turn_index` 1..N.

## Progress

- 2026-10-11: line "No modificar el código de referencia salvo que el ejercicio lo exija" removed from `CLAUDE.md` (assumption written by the agent, not Javi's rule).

- 2026-10-11: T1 and T2 implemented by delegated writer (strict TDD).
  - T1: `complete_structured_chat` now uses instructor `create_with_completion` and returns `tokens_in`, `tokens_out`, `cost_usd` (via `_estimate_cost`). Test added: `tests/test_llm_wrapper.py::test_complete_structured_chat_reports_tokens_and_cost`. The two existing structured-chat tests were repointed from `create` to `create_with_completion`.
  - T2: new `Session.turns_processed` counter (`app/sessions/models.py`), incremented once per conversational turn in `estimate_conversational`; `turn_index` reads it. Test added: `tests/test_turn_index.py::test_turn_index_keeps_growing_past_the_window` (10 turns, default window 6).
  - RED observed: new tests failed before the fix (`turn_index` stuck at 7; `tokens_in` missing from meta). GREEN after the fix.
  - `uv run pytest -q`: 176 passed.

- 2026-10-11: T3 implemented by delegated writer (strict TDD).
  - `evals/stress/run.py`: new `--turn-retries` flag (default 2) threaded into `_run_one_session(..., turn_retries=2)`; each failed attempt writes an error row, the same turn is re-sent, abort only after the last attempt fails. New `attempt` CSV column (1-based) on every row. `turn_index` stays empty on error rows (`ScenarioTurn` has no index).
  - Tests in `tests/test_stress_runner.py`: fail-once-then-succeed (attempts 1,2,1, session continues) and fail-every-attempt (3 error rows, abort). Existing error-row test now passes `turn_retries=0`.
  - RED: 3 failed (`unexpected keyword argument 'turn_retries'`). GREEN after the change.
  - `uv run pytest -q`: 178 passed.

- 2026-10-11: T4 implemented by delegated writer (strict TDD).
  - `evals/stress/scenarios.py`: new `CompetingFacts(old, new, introduced_at_turn)` and optional `Scenario.competing_facts` (pivot: React Native vs Flutter from turn 5; contradiction: 30000 variants vs 80000 variants from turn 8). Budget needles tightened "30"/"80" -> "30000"/"80000".
  - `evals/stress/run.py`: new CSV columns `facts_tracked`, `facts_recalled`, `fact_recall` (facts from turns 1..N-1, deduped by fact+field, empty recall when 0 tracked) and `old_fact_in`, `new_fact_in` (`|`-joined among summary/anchors/metadata, empty if none or not yet active). `tracked_fact`/`memory_drift_passed` unchanged.
  - Limitation: `GET /sessions/{id}` (`SessionInfoResponse`) exposes only metadata plus counts (`anchors_count`, `summary_chars`), not summary or anchor text. Today only `metadata` can ever appear in `old_fact_in`/`new_fact_in`, and `fact_field="any"` facts only match metadata. Fixing needs an app change (out of T4 scope).
  - Tests in `tests/test_stress_runner.py` (4 new). RED: 4 failed. GREEN after the change.
  - `uv run pytest -q`: 182 passed.

- 2026-10-11: T5 inline (strict TDD). Test `tests/test_session_snapshot.py`: RED `KeyError: 'summary'`, GREEN after adding `summary`/`anchors` to `SessionInfoResponse` (`app/routers/sessions.py`). `uv run pytest -q`: 183 passed.

## Next step

Javi rebuilds the container (app change in T5). Then pivot smoke run to check the new columns, then full runs A and B.
