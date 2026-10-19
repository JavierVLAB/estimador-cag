from types import SimpleNamespace

import pytest
import tiktoken
from fastapi.testclient import TestClient

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import OpenAIEmbedder
from app.embedding_pipeline.router import get_embedder
from app.embedding_pipeline.schemas import Budget, Chunk, EmbeddedChunk
from app.main import app


def _budget() -> Budget:
    return Budget.model_validate(
        {
            "budget_id": "BUD-2024-014",
            "client_metadata": {
                "name": "FintechCorp",
                "sector": "finance",
                "country": "ES",
            },
            "project_summary": "Mobile banking API with OAuth 2.0 authentication",
            "main_technology": "ruby_on_rails",
            "year": 2024,
            "total_estimated_hours": 480,
            "components": [
                {
                    "component_id": "AUTH-001",
                    "name": "OAuth 2.0 authentication backend",
                    "description": "JWT session management with client rate limiting.",
                    "tech_stack": ["ruby_on_rails", "postgresql", "redis"],
                    "estimated_hours": 120,
                    "complexity": "high",
                    "dependencies": [],
                },
                {
                    "component_id": "API-002",
                    "name": "Account API",
                    "description": "REST API for customer account balances.",
                    "tech_stack": ["ruby_on_rails", "postgresql"],
                    "estimated_hours": 80,
                    "complexity": "medium",
                    "dependencies": ["AUTH-001"],
                },
            ],
        }
    )


def test_budget_schema_accepts_normalized_budget() -> None:
    budget = _budget()

    assert budget.client_metadata.sector == "finance"
    assert budget.components[1].dependencies == ["AUTH-001"]


def test_chunker_makes_one_contextualized_chunk_per_component() -> None:
    chunks = JSONStructuralChunker().chunk([_budget()])

    assert [chunk.chunk_id for chunk in chunks] == [
        "BUD-2024-014::AUTH-001",
        "BUD-2024-014::API-002",
    ]
    first = chunks[0]
    assert "Mobile banking API with OAuth 2.0 authentication" in first.text
    assert "Client sector: finance" in first.text
    assert "Year: 2024" in first.text
    assert "Main tech: ruby_on_rails" in first.text
    assert "OAuth 2.0 authentication backend" in first.text
    assert "JWT session management with client rate limiting." in first.text
    assert "ruby_on_rails, postgresql, redis" in first.text
    assert "Complexity: high" in first.text
    assert "Estimated hours: 120" in first.text
    assert first.metadata == {
        "budget_id": "BUD-2024-014",
        "component_id": "AUTH-001",
        "client_sector": "finance",
        "main_technology": "ruby_on_rails",
        "year": 2024,
        "complexity": "high",
        "estimated_hours": 120,
    }
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")
    assert first.token_count == len(encoding.encode(first.text))


class _FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.calls.append({"model": model, "input": input})
        # Reverse the provider data deliberately: the adapter must use indexes.
        data = [
            SimpleNamespace(index=index, embedding=[float(index), 1.0])
            for index in reversed(range(len(input)))
        ]
        return SimpleNamespace(data=data)


class _FakeClient:
    def __init__(self) -> None:
        self.embeddings = _FakeEmbeddingsAPI()


def _chunks(count: int) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"budget::{index}",
            text=f"component {index}",
            metadata={"budget_id": "budget", "component_id": str(index)},
            token_count=index + 1,
        )
        for index in range(count)
    ]


def test_embedder_batches_chunks_and_preserves_chunk_order() -> None:
    client = _FakeClient()

    embedded = OpenAIEmbedder(client).embed(_chunks(101))

    assert [len(call["input"]) for call in client.embeddings.calls] == [100, 1]
    assert [item.chunk_id for item in embedded] == [f"budget::{index}" for index in range(101)]
    assert embedded[0].embedding == [0.0, 1.0]
    assert embedded[100].metadata["component_id"] == "100"


def test_embedder_retries_only_rate_limits_with_exponential_backoff() -> None:
    class FakeRateLimitError(Exception):
        pass

    class FlakyEmbeddingsAPI(_FakeEmbeddingsAPI):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
            self.attempts += 1
            if self.attempts < 3:
                raise FakeRateLimitError("slow down")
            return super().create(model=model, input=input)

    client = SimpleNamespace(embeddings=FlakyEmbeddingsAPI())
    waits: list[int] = []

    embedded = OpenAIEmbedder(
        client,
        sleep=waits.append,
        rate_limit_error=FakeRateLimitError,
    ).embed(_chunks(1))

    assert waits == [1, 2]
    assert len(embedded) == 1


def test_embedder_propagates_non_rate_limit_provider_errors() -> None:
    class BrokenEmbeddingsAPI:
        def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
            raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        OpenAIEmbedder(SimpleNamespace(embeddings=BrokenEmbeddingsAPI())).embed(_chunks(1))


class _EndpointEmbedder:
    def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        return [EmbeddedChunk(**chunk.model_dump(), embedding=[0.1, 0.2]) for chunk in chunks]


def test_ingest_endpoint_returns_embedded_chunks_and_aggregate_stats() -> None:
    app.dependency_overrides[get_embedder] = lambda: _EndpointEmbedder()
    try:
        with TestClient(app) as client:
            response = client.post("/embeddings/ingest", json={"budgets": [_budget().model_dump()]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["total_budgets"] == 1
    assert payload["stats"]["total_chunks"] == 2
    assert payload["stats"]["total_tokens"] > 0
    assert payload["stats"]["estimated_cost_usd"] > 0
    assert payload["chunks"][0]["chunk_id"] == "BUD-2024-014::AUTH-001"


def test_ingest_endpoint_maps_provider_errors_to_a_generic_500() -> None:
    class FailingEmbedder:
        def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
            raise RuntimeError("provider secret detail")

    app.dependency_overrides[get_embedder] = lambda: FailingEmbedder()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/embeddings/ingest", json={"budgets": [_budget().model_dump()]})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {"detail": "Embedding ingestion failed."}


def test_ingest_endpoint_keeps_fastapi_validation_errors() -> None:
    with TestClient(app) as client:
        response = client.post("/embeddings/ingest", json={"budgets": []})

    assert response.status_code == 422
