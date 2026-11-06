from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.embedding_pipeline.database import get_session
from app.embedding_pipeline.router import get_embedder, get_reranker
from app.main import app
from app.retrieval.search import search


def _row(chunk_id: int, distance: float = 0.5) -> SimpleNamespace:
    return SimpleNamespace(
        id=chunk_id,
        document_id=chunk_id * 10,
        chunk_type="component",
        content=f"chunk {chunk_id}",
        metadata_={"budget_id": f"BUD-{chunk_id}"},
        distance=distance,
    )


class _FakeSession:
    """Serves vector or lexical rows depending on the statement, honouring LIMIT."""

    def __init__(self, vector_ids: list[int], lexical_ids: list[int]) -> None:
        self.vector_rows = [_row(i) for i in vector_ids]
        self.lexical_rows = [_row(i) for i in lexical_ids]
        self.sql: list[str] = []
        self.limits: list[int] = []

    async def execute(self, statement):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        limit = statement._limit
        self.sql.append(sql)
        self.limits.append(limit)
        rows = self.lexical_rows if "@@" in sql else self.vector_rows
        return SimpleNamespace(all=lambda: rows[:limit])


class _FakeReranker:
    """Scores a chunk by its id, so higher ids win."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, documents: list[str]) -> list[float]:
        self.calls.append((query, documents))
        return [float(document.split()[-1]) for document in documents]


class _ExplodingReranker:
    def score(self, query: str, documents: list[str]) -> list[float]:
        raise AssertionError("the reranker must not run when reranking is off")


async def test_vector_mode_without_rerank_returns_top_k_by_distance() -> None:
    session = _FakeSession(vector_ids=[1, 2, 3, 4], lexical_ids=[])

    chunks = await search(session, "q", [0.1], k=2, mode="vector")

    assert [chunk.id for chunk in chunks] == [1, 2]
    assert session.limits == [2]
    assert "ORDER BY chunks.embedding <=>" in session.sql[0]
    assert all(chunk.rrf_score is None and chunk.rerank_score is None for chunk in chunks)


async def test_hybrid_mode_fuses_both_branches_without_duplicates() -> None:
    session = _FakeSession(vector_ids=[1, 2, 3], lexical_ids=[3, 4])

    chunks = await search(session, "stripe payments", [0.1], k=3, mode="hybrid")

    ids = [chunk.id for chunk in chunks]
    assert ids[0] == 3  # present in both lists: consensus wins
    assert len(ids) == len(set(ids)) == 3
    assert all(chunk.rrf_score is not None for chunk in chunks)
    assert session.limits == [50, 50]  # each branch recalls its top 50


async def test_lexical_branch_matches_any_term_with_english_config() -> None:
    session = _FakeSession(vector_ids=[], lexical_ids=[1])

    await search(session, "online store", [0.1], k=1, mode="hybrid")

    lexical_sql = next(sql for sql in session.sql if "@@" in sql)
    assert "plainto_tsquery" in lexical_sql
    assert "replace(" in lexical_sql  # AND (&) swapped for OR (|)
    assert "ts_rank(chunks.content_tsv" in lexical_sql


async def test_rerank_recalls_50_and_keeps_the_best_k() -> None:
    session = _FakeSession(vector_ids=list(range(1, 61)), lexical_ids=[])
    reranker = _FakeReranker()

    chunks = await search(session, "q", [0.1], k=5, mode="vector", reranker=reranker)

    assert session.limits == [50]
    assert len(reranker.calls[0][1]) == 50
    assert [chunk.id for chunk in chunks] == [50, 49, 48, 47, 46]
    assert chunks[0].rerank_score == 50.0


async def test_hybrid_with_rerank_reranks_the_fused_candidates() -> None:
    session = _FakeSession(vector_ids=[1, 2], lexical_ids=[2, 9])
    reranker = _FakeReranker()

    chunks = await search(session, "q", [0.1], k=2, mode="hybrid", reranker=reranker)

    assert sorted(reranker.calls[0][1]) == ["chunk 1", "chunk 2", "chunk 9"]
    assert [chunk.id for chunk in chunks] == [9, 2]
    assert all(chunk.rrf_score is not None for chunk in chunks)


def _post(payload: dict, session: _FakeSession, reranker) -> dict:
    class Embedder:
        def embed_one(self, text: str) -> list[float]:
            return [0.1]

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_embedder] = lambda: Embedder()
    app.dependency_overrides[get_reranker] = lambda: reranker
    try:
        with TestClient(app) as client:
            response = client.post("/search", json=payload)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    return response.json()


def test_endpoint_defaults_to_vector_without_rerank_and_omits_new_scores() -> None:
    session = _FakeSession(vector_ids=[1, 2], lexical_ids=[2])

    payload = _post({"query": "q", "k": 2}, session, _ExplodingReranker())

    assert [result["chunk_id"] for result in payload["results"]] == [1, 2]
    assert "rrf_score" not in payload["results"][0]
    assert "rerank_score" not in payload["results"][0]
    assert len(session.sql) == 1


def test_endpoint_runs_hybrid_and_rerank_when_requested() -> None:
    session = _FakeSession(vector_ids=[1, 2], lexical_ids=[2, 3])

    payload = _post(
        {"query": "q", "k": 2, "mode": "hybrid", "rerank": True}, session, _FakeReranker()
    )

    results = payload["results"]
    assert [result["chunk_id"] for result in results] == [3, 2]
    assert {"rrf_score", "rerank_score"} <= results[0].keys()


def test_endpoint_rejects_unknown_mode() -> None:
    with TestClient(app) as client:
        response = client.post("/search", json={"query": "q", "mode": "bm25"})

    assert response.status_code == 422
