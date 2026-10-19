## ADDED Requirements

### Requirement: Structural budget chunking
The system SHALL convert every component of every submitted normalized budget into
exactly one chunk with identifier `{budget_id}::{component_id}`. Each chunk text MUST
include parent project summary, client sector, year, main technology, component name,
description, technology stack, complexity, and estimated hours. Each chunk metadata
MUST include `budget_id`, `component_id`, `client_sector`, `main_technology`, `year`,
`complexity`, and `estimated_hours`, and its token count MUST use the
`text-embedding-3-small` encoding.

#### Scenario: A budget contains multiple components
- **WHEN** ingestion receives a valid budget with two components
- **THEN** the chunker returns two traceable chunks whose texts include the shared
  parent context and whose metadata retains the component-specific filter fields

### Requirement: Batched OpenAI embeddings
The system SHALL embed chunk texts with `text-embedding-3-small` at the provider's
default dimensions. It MUST submit no more than 100 inputs per provider request,
preserve each chunk's identity and metadata in the embedded output, and log the
chunk count, total tokens, and latency for every processed batch. On `RateLimitError`,
it MUST retry with waits of 1, 2, and 4 seconds before surfacing the error.

#### Scenario: Ingestion crosses a batch boundary
- **WHEN** the embedder receives 101 chunks
- **THEN** it issues two provider requests containing at most 100 inputs each and
  returns 101 embedded chunks in input order

### Requirement: Stateless embedding ingestion endpoint
The service SHALL expose `POST /embeddings/ingest`, accepting an `IngestRequest` JSON
body and returning an `IngestResponse` with embedded chunks plus `total_budgets`,
`total_chunks`, `total_tokens`, and `estimated_cost_usd`. Invalid payloads MUST use
FastAPI's 422 validation response. Unexpected provider failures MUST be logged with
detail and return a generic HTTP 500 response without persisting chunks or vectors.

#### Scenario: Valid budget ingestion
- **WHEN** a client posts a valid normalized budget payload to `/embeddings/ingest`
- **THEN** the service responds with 200 and the vectorized chunks and aggregate
  statistics derived from that request

#### Scenario: Provider failure during ingestion
- **WHEN** the provider raises an unexpected embedding error
- **THEN** the service logs the failure and responds with HTTP 500 and a generic
  client-safe message
