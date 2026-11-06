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
- Dataset: the official `data/budgets_sample.json` was imported from the course
  branch `session_07`. Its SHA-256 is
  `64c2a2372a3cf30c55fcc8d7aaf04c73b9caea64dcb474348eeb6d5253970392`.
  Do not replace it with an invented substitute.
- The three prescribed OpenAI comparisons were authorized and completed with the
  configured local credential; do not make further provider calls outside that
  recorded scope without explicit authorization.

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
- [x] T2 — Implement batched OpenAI embedding and the stateless FastAPI ingestion
  endpoint, including error mapping and router registration. Route: delegated.
  Trigger: writer (embedder, router, app composition, tests). Checks: strict TDD
  RED/GREEN with provider fakes; focused pytest. Estimated 160 lines.
- [x] T3 — Implement the reusable cosine-similarity CLI and update README execution
  instructions. Route: delegated. Trigger: writer (CLI, docs, tests). Checks: strict
  TDD RED/GREEN for CLI math/arguments; focused pytest. Estimated 90 lines.
- [x] T4 — Add the official course sample dataset and validate it against the input
  contract. Route: delegated. Trigger: data source supplied after prior external
  review. Checks: `Budget.model_validate` observed for all records (15 budgets, 52
  components); focused and full offline pytest passed. The live endpoint was not
  invoked because it would call OpenAI; that verification remains under T5. Commit:
  `1258273 feat(embeddings): add course budget dataset`.
- [x] T5 — Run the three specified live OpenAI comparisons and record
  `SANITY_CHECK.md`. Route: delegated after explicit remote-operation authorization
  and an authorized credential session. Trigger: external operation authorization.
  Checks: all three outputs recorded with interpretation. Evidence commit:
  `f04c3d6 docs(embeddings): record live sanity check`. Estimated 20 lines.
- [ ] T6 — Repair direct `scripts/compare.py` execution, update its documented
  invocation, rebuild Docker, and verify the route appears in Swagger. Route:
  delegated. Trigger: writer (script, regression test, README) and preparation.
  Checks: strict TDD RED/GREEN for `uv run python scripts/compare.py --help`, full
  pytest, Docker build, and non-embedding `/docs` verification. The direct-command
  regression is green and `/docs` returns 200 with `POST /embeddings/ingest` in
  OpenAPI; a fresh Docker rebuild remains pending because DNS could not resolve
  `ghcr.io` while pulling the `uv` image. Estimated 40 lines.

## Acceptance criteria

- `POST /embeddings/ingest` returns contextualized, embedded component chunks with
  aggregate totals and a current labelled cost estimate.
- The adapter batches no more than 100 texts and retries OpenAI rate limits with the
  specified exponential waits.
- The CLI prints two inputs and their standard-library cosine similarity.
- Existing test suite passes and new focused tests show observed RED then GREEN.
- The official dataset is present and schema-validated; the three authorized live
  OpenAI sanity checks are recorded in `SANITY_CHECK.md`.

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
- 2026-10-19: T2 delegated under strict TDD. Observed RED:
  `uv run pytest tests/test_embedding_pipeline.py -q` failed with
  `ModuleNotFoundError: app.embedding_pipeline.embedder`. GREEN: the focused command
  reported `8 passed in 0.04s`; `uv run pytest -q` reported `205 passed in 0.61s`;
  Ruff and `git diff --check` passed. Commit `3c5a413 feat(embeddings): add ingestion
  endpoint` adds the batched/retrying adapter, typed endpoint, router registration,
  and offline provider fakes. The accumulated RDD candidate (797 lines) was reviewed
  by the native reliability lens with no findings and acknowledged as approved;
  reviewed boundary: `3c5a413`.
- 2026-10-19: T3 delegated under strict TDD. Observed RED: focused tests first failed
  because the `scripts` package did not exist, then because README lacked the
  ingestion endpoint instructions. GREEN: `12 passed` focused and `209 passed` for
  `uv run pytest -q`; Ruff and `git diff --check` passed. Commit `c4efae9
  feat(embeddings): add similarity comparison CLI` adds `compare.py`, the public
  `embed_one`/`embed_many` adapter methods, tests, and local/Docker usage docs.
  Runtime Docker and live OpenAI checks were not run: they remain blocked by the
  missing course dataset and external-operation authorization. The four native review
  lenses (risk, resilience, readability, reliability) found no issues and were
  acknowledged as approved; reviewed boundary: `c4efae9`.
- 2026-10-19: T4 delegated after the official course branch was supplied. The exact
  `data/budgets_sample.json` was imported with SHA-256
  `64c2a2372a3cf30c55fcc8d7aaf04c73b9caea64dcb474348eeb6d5253970392`.
  Local schema validation observed 15 budgets and 52 components; focused pytest
  reported `12 passed`, full pytest `209 passed`, and `git diff --check` passed.
  No live endpoint call occurred because that would invoke OpenAI. Commit `1258273
  feat(embeddings): add course budget dataset`. The native reliability review found
  no defects and was acknowledged as approved.
- 2026-10-19 19:07 CEST: T5 ran exactly the three user-authorized OpenAI comparison
  pairs via `uv run python -m scripts.compare` with the configured local `.env`
  credential. Results were A `0.595734`, B `0.191966`, and C `0.540708`; the exact
  commands, values, and a four-line interpretation are in
  `app/embedding_pipeline/SANITY_CHECK.md`. The user also manually verified
  `POST /embeddings/ingest` in Swagger with `BUD-2024-001`, receiving four
  contextualized embedded chunks. T6 (Docker rebuild/Swagger runtime verification)
  remains pending because it was not included in this task's authorized scope.
- 2026-10-19: T6 observed RED with `uv run pytest
  tests/test_embedding_pipeline.py::test_compare_script_runs_directly_for_help -q`:
  direct execution failed with `ModuleNotFoundError: app`. The script now adds the
  repository root only when executed as a file; GREEN reported `1 passed`, then
  `13 passed` focused and `210 passed` full. `uv run python scripts/compare.py
  --help`, Ruff, and `git diff --check` passed. The Docker image now copies
  `scripts/`, but `docker compose up --build -d` could not resolve `ghcr.io` to pull
  `ghcr.io/astral-sh/uv:latest`; the existing healthy container nevertheless served
  `/docs` with HTTP 200 and its OpenAPI declared `POST /embeddings/ingest`. No
  embedding endpoint or OpenAI call occurred. Fresh-image verification remains
  pending network recovery.

## Next step

Retry the Docker rebuild once DNS access to `ghcr.io` is restored, then verify that
the rebuilt image includes `scripts/compare.py`; no embedding request is required.
