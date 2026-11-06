"""Chunk retrieval: vector, lexical and hybrid rankings, optionally reranked.

Recall-then-rerank: when reranking is on, the cheap branches recall a wide
candidate set (``recall_k``) and the cross-encoder keeps the best ``k``. Without
reranking, each mode returns its own top ``k`` directly.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Text, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession

from app.embedding_pipeline.models import Chunk
from app.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion

SearchMode = Literal["vector", "hybrid"]

# Must match the configuration of the generated `content_tsv` column.
TEXT_SEARCH_CONFIG = "english"
DEFAULT_RECALL_K = 50


class Reranker(Protocol):
    """What the search needs from CrossEncoderReranker: one score per document."""

    def score(self, query: str, documents: list[str]) -> list[float]: ...


@dataclass
class RetrievedChunk:
    """One chunk with the scores of every stage it went through."""

    id: int
    document_id: int
    chunk_type: str
    content: str
    metadata_: dict[str, Any]
    distance: float
    rrf_score: float | None = None
    rerank_score: float | None = None


def _columns(query_vector: list[float]):
    distance = Chunk.embedding.cosine_distance(query_vector)
    return distance, (
        Chunk.id,
        Chunk.document_id,
        Chunk.chunk_type,
        Chunk.content,
        Chunk.metadata_,
        distance.label("distance"),
    )


def _to_chunk(row) -> RetrievedChunk:
    return RetrievedChunk(
        id=row.id,
        document_id=row.document_id,
        chunk_type=row.chunk_type,
        content=row.content,
        metadata_=row.metadata_,
        distance=row.distance,
    )


def any_term_tsquery(query: str):
    """OR of the query lexemes.

    plainto_tsquery joins lexemes with AND, so a long project description would
    match almost nothing; swapping the operator lets ts_rank reward chunks that
    contain more of the terms.
    """
    and_query = func.plainto_tsquery(TEXT_SEARCH_CONFIG, query)
    return func.replace(and_query.cast(Text), "&", "|").cast(TSQUERY)


async def vector_search(
    session: AsyncSession, query_vector: list[float], limit: int
) -> list[RetrievedChunk]:
    """Top chunks by cosine distance (exact scan, no vector index)."""
    # `<=>` (cosine) must match the operator class of the index created live
    # (vector_cosine_ops); otherwise Postgres silently falls back to a seq scan.
    distance, columns = _columns(query_vector)
    stmt = select(*columns).order_by(distance).limit(limit)
    return [_to_chunk(row) for row in (await session.execute(stmt)).all()]


async def lexical_search(
    session: AsyncSession, query: str, query_vector: list[float], limit: int
) -> list[RetrievedChunk]:
    """Top chunks by ts_rank over `content_tsv`; carries the cosine distance too."""
    tsquery = any_term_tsquery(query)
    _, columns = _columns(query_vector)
    stmt = (
        select(*columns)
        .where(Chunk.content_tsv.op("@@")(tsquery))
        .order_by(func.ts_rank(Chunk.content_tsv, tsquery).desc(), Chunk.id)
        .limit(limit)
    )
    return [_to_chunk(row) for row in (await session.execute(stmt)).all()]


async def hybrid_search(
    session: AsyncSession,
    query: str,
    query_vector: list[float],
    limit: int,
    *,
    branch_k: int = DEFAULT_RECALL_K,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[RetrievedChunk]:
    """Fuse the vector and lexical top ``branch_k`` with RRF and keep ``limit``."""
    semantic = await vector_search(session, query_vector, branch_k)
    lexical = await lexical_search(session, query, query_vector, branch_k)
    by_id = {chunk.id: chunk for chunk in [*semantic, *lexical]}
    fused = reciprocal_rank_fusion(
        [[chunk.id for chunk in semantic], [chunk.id for chunk in lexical]], k=rrf_k
    )
    results = []
    for chunk_id, score in fused[:limit]:
        chunk = by_id[chunk_id]
        chunk.rrf_score = score
        results.append(chunk)
    return results


async def search(
    session: AsyncSession,
    query: str,
    query_vector: list[float],
    *,
    k: int,
    mode: SearchMode = "vector",
    reranker: Reranker | None = None,
    recall_k: int = DEFAULT_RECALL_K,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[RetrievedChunk]:
    """Return the final top ``k`` chunks for one configuration.

    Passing a ``reranker`` turns on recall-then-rerank; ``None`` skips it, so the
    model is never loaded.
    """
    limit = max(recall_k, k) if reranker is not None else k
    if mode == "hybrid":
        candidates = await hybrid_search(
            session, query, query_vector, limit, branch_k=max(recall_k, k), rrf_k=rrf_k
        )
    else:
        candidates = await vector_search(session, query_vector, limit)

    if reranker is None or not candidates:
        return candidates

    # The cross-encoder is CPU-bound and synchronous; keep it off the event loop.
    scores = await run_in_threadpool(
        reranker.score, query, [chunk.content for chunk in candidates]
    )
    for chunk, score in zip(candidates, scores):
        chunk.rerank_score = score
    # Stable sort: equal scores keep their recall order.
    ranked = sorted(candidates, key=lambda chunk: chunk.rerank_score, reverse=True)
    return ranked[:k]
