# exercise-07-embeddings

## Objective

Implement the Session 07 minimum embeddings pipeline on `session-07/pre-exercise`:
accept normalized budgets, create structural chunks, embed them with OpenAI, expose
them over HTTP, and provide a cosine-similarity CLI. Do not add retrieval, vector
persistence, or UI changes.

## Problem and why

The service has historical budgets as structured JSON but no semantic representation
for the next course session. The exercise requires a small, inspectable in-memory
ingestion path that prepares the data without pre-empting the later pgvector and
retrieval work.

## Authorized scope and constraints

- Authorized: source, tests, dependency, CLI, router, documentation, and local
  course evidence required by OpenSpec change `exercise-07-embeddings`.
- Excluded: Streamlit/Rails, current estimation/session behavior, vector databases,
  retrieval, alternate chunkers, provider/model comparison, and enrichment LLMs.
- Dataset: the official `data/budgets_sample.json` is absent; do not invent or
  represent a substitute as course-provided data. Continue independently runnable
  work and leave dataset-dependent validation pending.
- External OpenAI invocations are not authorized by this local implementation request;
  do not run the live sanity checks without explicit destination, operation, and
  credential-session authorization.

## Delivery and TDD

- TDD: strict, enabled. Source: existing project session record in
  `odd/tasks/fix-turn-observation.md`. Runner: `uv run pytest`.
- Forecast: approximately 350 authored changed lines excluding the unavailable course
  dataset and recorded live output.
- Delivery strategy: `ask-on-risk`; no pull request is authorized. Work-unit commits
  use Conventional Commit messages on this feature branch.
- Engram locator: `odd/exercise-07-embeddings/tasks`; mirror is to be saved after this
  file is read back.

## Tasks

- [x] T1 — Implement the typed embedding pipeline foundation: add `tiktoken`,
  schemas, and the structural chunker. Route: delegated. Trigger: writer (two
  non-trivial files) and preparation work. Checks: strict TDD RED/GREEN for schemas
  and chunk construction; focused pytest. Estimated 100 lines.
- [ ] T2 — Implement batched OpenAI embedding and the stateless FastAPI ingestion
  endpoint, including error mapping and router registration. Route: delegated.
  Trigger: writer (embedder, router, app composition, tests). Checks: strict TDD
  RED/GREEN with provider fakes; focused pytest. Estimated 160 lines.
- [ ] T3 — Implement the reusable cosine-similarity CLI and update README execution
  instructions. Route: delegated. Trigger: writer (CLI, docs, tests). Checks: strict
  TDD RED/GREEN for CLI math/arguments; focused pytest. Estimated 90 lines.
- [ ] T4 — Add the official course sample dataset and validate it against the API
  contract. Route: delegated after the data source is supplied. Trigger: data input
  unavailable. Checks: schema validation and endpoint invocation. Estimated 30 lines.
- [ ] T5 — Run the three specified live OpenAI comparisons and record
  `SANITY_CHECK.md`. Route: delegated after explicit remote-operation authorization
  and an authorized credential session. Trigger: external operation authorization.
  Checks: all three outputs recorded with interpretation. Estimated 20 lines.

## Acceptance criteria

- `POST /embeddings/ingest` returns contextualized, embedded component chunks with
  aggregate totals and a current labelled cost estimate.
- The adapter batches no more than 100 texts and retries OpenAI rate limits with the
  specified exponential waits.
- The CLI prints two inputs and their standard-library cosine similarity.
- Existing test suite passes and new focused tests show observed RED then GREEN.
- Dataset and live-sanity items remain honestly pending until their prerequisites are
  supplied and authorized.

## Progress and evidence

- 2026-10-19: Branch `session-07/pre-exercise` and OpenSpec proposal complete.
- 2026-10-19: Implementation authorized without the official dataset. T1–T3 can
  proceed; T4–T5 are explicitly pending external prerequisites.
- 2026-10-19: T1 delegated under strict TDD. Observed RED:
  `uv run pytest tests/test_embedding_pipeline.py -q` failed collection with
  `ModuleNotFoundError: app.embedding_pipeline`. GREEN: the same command reported
  `2 passed in 0.27s`; `uv run pytest -q` reported `199 passed in 0.67s`; Ruff and
  `git diff --check` passed. Commit `85b40f8 feat(embeddings): add structural budget
  chunker` adds the schemas, tiktoken-backed chunker, lockfile, and focused tests.
  RDD assessment: medium, 207 authored lines, `under_budget`; no review is due yet
  and the reviewed boundary remains `8975aa6` for the accumulated slice.

## Next step

Delegate T2 embedding adapter and ingestion endpoint under strict TDD. Keep the
accumulated review slice based at `8975aa6` until native review becomes due.
