## Why

The service has normalized historical software budgets but cannot yet represent their
meaning for future semantic retrieval. This exercise introduces the smallest
end-to-end embeddings pipeline so the course can compare chunking approaches in the
live session without coupling the result to a vector database or the user interface.

## What Changes

- Add a structural JSON budget chunker that produces one contextualized chunk per
  budget component and records filterable metadata and token counts.
- Add a batched OpenAI embedding adapter using `text-embedding-3-small`, including
  basic rate-limit retries, structured logs, and estimated input cost.
- Expose `POST /embeddings/ingest` to vectorize submitted normalized budgets in
  memory and return chunks plus aggregate statistics.
- Add a command-line similarity checker that reuses the adapter and calculates
  cosine similarity with the Python standard library.
- Add the course sample budgets, a recorded three-pair sanity check, and README
  instructions for Docker and local execution.

## Capabilities

### New Capabilities

- `budget-embedding-ingestion`: Convert normalized historical budget components into
  contextual, token-counted embedded chunks through a FastAPI endpoint.
- `embedding-similarity-cli`: Compare two command-line text inputs using the shared
  embedding adapter and cosine similarity.

### Modified Capabilities

- None.

## Impact

- New package: `app/embedding_pipeline/` and its `POST /embeddings/ingest` router.
- Application composition changes in `app/main.py` to register the new router.
- New `scripts/compare.py`, sample data, sanity-check evidence, and README usage
  documentation.
- Dependency change: add `tiktoken`; `openai` is already declared.
- No persistence, retrieval, Streamlit, Rails, or existing estimation/session API
  behavior changes.
