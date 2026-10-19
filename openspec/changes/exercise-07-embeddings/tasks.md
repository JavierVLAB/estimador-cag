## 1. Foundation and structural chunking

- [x] 1.1 Add `tiktoken`, create the `app/embedding_pipeline` package, and define
  Pydantic models for normalized budgets, chunks, embeddings, and ingestion payloads.
- [x] 1.2 Implement `JSONStructuralChunker` with one contextualized, token-counted
  chunk per budget component and the specified filterable metadata.
- [ ] 1.3 Add the course-provided `data/budgets_sample.json` and validate that its
  records conform to the ingestion contract.

## 2. Embedding ingestion

- [ ] 2.1 Implement `OpenAIEmbedder` with `text-embedding-3-small`, batches of at
  most 100 inputs, rate-limit backoff, batch telemetry, and cost estimation.
- [ ] 2.2 Add `POST /embeddings/ingest`, generic provider-error handling, and router
  registration in the FastAPI application.
- [ ] 2.3 Run focused offline checks for schemas, chunking, batching, and endpoint
  error mapping, then run the existing test suite to detect regressions.

## 3. CLI, evidence, and documentation

- [ ] 3.1 Add `scripts/compare.py` using the shared embedder and standard-library
  cosine similarity.
- [ ] 3.2 Execute the three prescribed live comparisons and record their numeric
  output and interpretation in `app/embedding_pipeline/SANITY_CHECK.md`.
- [ ] 3.3 Update the README with endpoint and CLI instructions for Docker and local
  `uv` execution; rebuild the Docker service and verify the endpoint in `/docs`.
