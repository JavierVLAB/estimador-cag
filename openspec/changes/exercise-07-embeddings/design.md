## Context

The FastAPI service already accepts typed estimation input and uses OpenAI through
existing service abstractions. Historical budgets are now available as normalized
JSON, but the application has no representation suitable for semantic search. The
exercise needs an in-memory ingestion boundary only: PostgreSQL/pgvector, retrieval,
and UI integration are intentionally deferred.

The implementation must fit the existing Pydantic v2, structlog, Docker, and
configuration conventions. `openai` is already a project dependency; token counting
requires adding `tiktoken`.

## Goals / Non-Goals

**Goals:**

- Convert each normalized budget component into one traceable, contextualized chunk.
- Count the model tokens for every chunk before sending it to OpenAI.
- Embed chunks efficiently in bounded batches and return them through a typed HTTP
  contract with aggregate statistics.
- Provide a small reusable CLI for inspecting cosine similarity.
- Leave reproducible manual evidence that the model distinguishes the prescribed
  similar, unrelated, and generic text pairs.

**Non-Goals:**

- Vector persistence, semantic retrieval, ranking metrics, or changes to existing
  estimation/session endpoints.
- Alternate chunking strategies, description splitting/overlap, enrichment by an
  LLM, model comparisons, or reduced embedding dimensions.
- Streamlit or Rails changes.

## Decisions

### One component is one chunk with parent context in its text

`JSONStructuralChunker` will iterate budgets and components and emit
`{budget_id}::{component_id}` identifiers. Its text includes project summary, client
sector, year, main technology, and the component fields; its metadata carries only
filterable values. This preserves the budget's semantic context without embedding an
opaque JSON serialization. Fixed-size/recursive splitting was rejected because the
exercise explicitly uses document structure as the chunk boundary.

### Pydantic models define the boundary at input and output

`Budget`, `BudgetComponent`, `Chunk`, `EmbeddedChunk`, `IngestRequest`, and
`IngestResponse` live together in `schemas.py`. The endpoint receives a JSON body
and FastAPI supplies 422 responses for invalid payloads. This keeps transport and
chunking inputs explicit instead of coupling the router to raw dictionaries.

### The adapter owns OpenAI batching, retrying, and telemetry

`OpenAIEmbedder` uses `text-embedding-3-small` at its default 1536 dimensions and
sends up to 100 chunk texts in each `embeddings.create` call. It retries only
`RateLimitError` after 1, 2, and 4 seconds; other provider errors propagate to the
router, which logs detail and returns a generic HTTP 500. Batching is preferred over
per-chunk requests for throughput and rate-limit resilience. A module constant makes
the $0.02-per-million-input-token estimate visible and easy to revise.

### Router orchestration stays thin and stateless

`POST /embeddings/ingest` performs chunk → batch embed → response assembly, with no
database write. The router is registered in `app.main`, matching the existing router
composition. The output exposes the vectors only for this pre-exercise; session 08
will own persistence.

### CLI reuses the adapter and the standard library

`scripts/compare.py` parses `--text-a` and `--text-b`, invokes `embed_one`, and
calculates cosine similarity with dot products and `math.sqrt`. It intentionally
does not introduce NumPy or scikit-learn.

## Risks / Trade-offs

- [Live OpenAI calls require a valid key and consume quota] → Keep automated checks
  offline, document the prerequisite, and record the three manual checks separately.
- [OpenAI pricing can change] → Isolate the current price in one labelled constant.
- [A component can be unusually large] → Return `token_count` unchanged so the live
  session can examine it; do not silently split or truncate it.
- [Returned embeddings can make large responses] → This is intentional and bounded
  to this in-memory exercise; persistence/retrieval is deferred.
- [Retries add latency] → Retry only rate limits, cap attempts at three, and log each
  batch so failures remain diagnosable.

## Migration Plan

1. Add the package, dependency, sample data, CLI, router registration, documentation,
   and sanity-check evidence on `session-07/pre-exercise`.
2. Rebuild the `servicio_ia` Docker image so `tiktoken` is installed.
3. Validate the endpoint from Swagger or an HTTP client and run the three CLI pairs
   with a configured `OPENAI_API_KEY`.
4. Roll back by reverting the feature's work-unit commits; no data migration or
   external state cleanup is necessary because ingestion is stateless.

## Open Questions

- The sample `data/budgets_sample.json` must be sourced from the course material; it
  is not present in the current repository. Its exact 15-record contents are needed
  before the runnable dataset can be committed.
