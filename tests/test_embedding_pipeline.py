from types import SimpleNamespace
from pathlib import Path
import subprocess
import sys

import pytest
import tiktoken
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import OpenAIEmbedder
from app.embedding_pipeline.database import get_session
from app.embedding_pipeline.models import Document
from app.embedding_pipeline.router import get_embedder
from app.embedding_pipeline.schemas import Budget, Chunk, EmbeddedChunk
from app.main import app
from scripts.compare import cosine_similarity, main as compare_main


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


def test_embedder_exposes_single_and_many_chunk_embedding_methods() -> None:
    embedder = OpenAIEmbedder(_FakeClient())

    assert embedder.embed_one("a standalone text") == [0.0, 1.0]
    assert [chunk.chunk_id for chunk in embedder.embed_many(_chunks(1))] == ["budget::0"]


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
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        return [EmbeddedChunk(**chunk.model_dump(), embedding=[0.1, 0.2]) for chunk in chunks]

    def embed_one(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.3, 0.4]


class _FakeTransaction:
    def __init__(self, session: "_FakeSession") -> None:
        self._session = session

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self._session.committed.extend(self._session.pending)
        else:
            self._session.rolled_back = True
        self._session.pending = []
        return False


class _FakeSession:
    """Just enough of AsyncSession to exercise the endpoint transaction logic."""

    def __init__(self, existing_document_id: int | None = None, rows: list | None = None) -> None:
        self.existing_document_id = existing_document_id
        self.rows = rows or []
        self.pending: list[object] = []
        self.committed: list[object] = []
        self.rolled_back = False
        self.statements: list[object] = []

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction(self)

    async def scalar(self, statement: object) -> int | None:
        return self.existing_document_id

    def add(self, instance: object) -> None:
        self.pending.append(instance)

    def add_all(self, instances) -> None:
        self.pending.extend(instances)

    async def flush(self) -> None:
        for instance in self.pending:
            if isinstance(instance, Document):
                instance.id = 7

    async def execute(self, statement: object) -> SimpleNamespace:
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: self.rows)


def _post(path: str, payload: dict, session: _FakeSession, embedder: object):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_embedder] = lambda: embedder
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.post(path, json=payload)
    finally:
        app.dependency_overrides.clear()


def _ingest_payload() -> dict:
    return {
        "source_path": "data/budgets_sample.json#BUD-2024-014",
        "document_type": "historical_budget",
        "content": _budget().model_dump(),
    }


def test_ingest_endpoint_persists_document_and_chunks_in_one_transaction() -> None:
    session = _FakeSession()

    response = _post("/embeddings/ingest", _ingest_payload(), session, _EndpointEmbedder())

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == 7
    assert payload["chunks_created"] == 2
    assert payload["embedding_dimension"] == 1536
    assert payload["ingestion_time_ms"] >= 0
    document, *chunks = session.committed
    assert isinstance(document, Document)
    assert document.source_path == "data/budgets_sample.json#BUD-2024-014"
    assert document.metadata_["sector"] == "finance"
    assert [chunk.chunk_type for chunk in chunks] == ["component", "component"]
    assert all(chunk.document_id == 7 for chunk in chunks)
    assert chunks[0].embedding == [0.1, 0.2]
    assert chunks[0].metadata_["chunk_key"] == "BUD-2024-014::AUTH-001"


def test_ingest_endpoint_returns_409_for_an_already_ingested_source_path() -> None:
    session = _FakeSession(existing_document_id=3)

    response = _post("/embeddings/ingest", _ingest_payload(), session, _EndpointEmbedder())

    assert response.status_code == 409
    assert response.json() == {"detail": "Document already ingested", "document_id": 3}
    assert session.committed == []


def test_ingest_endpoint_rolls_back_and_returns_generic_500_when_embedder_fails() -> None:
    class FailingEmbedder:
        def embed(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
            raise RuntimeError("provider secret detail")

    session = _FakeSession()

    response = _post("/embeddings/ingest", _ingest_payload(), session, FailingEmbedder())

    assert response.status_code == 500
    assert response.json() == {"detail": "Embedding ingestion failed."}
    assert session.rolled_back
    assert session.committed == []


def test_ingest_endpoint_keeps_fastapi_validation_errors() -> None:
    with TestClient(app) as client:
        response = client.post("/embeddings/ingest", json={"source_path": "x"})

    assert response.status_code == 422


def test_search_endpoint_ranks_by_cosine_distance_and_maps_rows() -> None:
    rows = [
        SimpleNamespace(
            id=11,
            document_id=7,
            chunk_type="component",
            content="Component: OAuth 2.0 authentication backend",
            metadata_={"budget_id": "BUD-2024-014"},
            distance=0.1234,
        )
    ]
    session = _FakeSession(rows=rows)
    embedder = _EndpointEmbedder()

    response = _post("/search", {"query": "JWT auth", "k": 3}, session, embedder)

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "JWT auth"
    assert payload["k"] == 3
    assert payload["search_time_ms"] >= 0
    assert payload["results"] == [
        {
            "chunk_id": 11,
            "document_id": 7,
            "chunk_type": "component",
            "content": "Component: OAuth 2.0 authentication backend",
            "distance": 0.1234,
            "metadata": {"budget_id": "BUD-2024-014"},
        }
    ]
    assert embedder.queries == ["JWT auth"]
    sql = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "ORDER BY chunks.embedding <=>" in sql
    assert "LIMIT" in sql


def test_search_endpoint_rejects_non_positive_k() -> None:
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "anything", "k": 0})

    assert response.status_code == 422


def test_compare_cli_prints_both_inputs_and_standard_library_cosine(capsys: pytest.CaptureFixture[str]) -> None:
    class FakeEmbedder:
        def __init__(self) -> None:
            self.inputs: list[str] = []

        def embed_one(self, text: str) -> list[float]:
            self.inputs.append(text)
            return {"first text": [1.0, 0.0], "second text": [0.5, 0.5]}[text]

    embedder = FakeEmbedder()

    assert compare_main(["--text-a", "first text", "--text-b", "second text"], embedder=embedder) == 0
    assert embedder.inputs == ["first text", "second text"]
    assert capsys.readouterr().out == (
        "Text A: first text\nText B: second text\nCosine similarity: 0.707107\n"
    )


def test_cosine_similarity_rejects_zero_and_mismatched_vectors() -> None:
    with pytest.raises(ValueError, match="same dimension"):
        cosine_similarity([1.0], [1.0, 2.0])
    with pytest.raises(ValueError, match="non-zero"):
        cosine_similarity([0.0], [1.0])


def test_compare_script_runs_directly_for_help() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/compare.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--text-a" in result.stdout


def test_readme_documents_embedding_endpoint_and_cli_commands() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "POST /embeddings/ingest" in readme
    assert "docker compose exec estimator python scripts/compare.py" in readme
    assert "uv run python scripts/compare.py" in readme
