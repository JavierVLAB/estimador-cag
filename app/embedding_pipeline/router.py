"""HTTP boundary that persists budget embeddings in pgvector and searches them."""

from functools import lru_cache
from time import perf_counter

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_openai_client
from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.database import get_session
from app.embedding_pipeline.embedder import OpenAIEmbedder
from app.embedding_pipeline.models import EMBEDDING_DIMENSION, Chunk, Document
from app.embedding_pipeline.schemas import (
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.search import search

log = structlog.get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])
search_router = APIRouter(tags=["search"])

# The structural chunker emits one chunk per budget component.
COMPONENT_CHUNK_TYPE = "component"


def get_embedder() -> OpenAIEmbedder:
    """Build the adapter at request time so endpoint tests can replace it."""
    return OpenAIEmbedder(get_openai_client())


def get_chunker() -> JSONStructuralChunker:
    """Build the stateless structural chunker for one ingestion request."""
    return JSONStructuralChunker()


@router.post("/ingest", response_model=IngestResponse, responses={409: {}})
async def ingest_budget(
    request: IngestRequest,
    session: AsyncSession = Depends(get_session),
    chunker: JSONStructuralChunker = Depends(get_chunker),
    embedder: OpenAIEmbedder = Depends(get_embedder),
) -> IngestResponse | JSONResponse:
    """Persist one budget and its embedded chunks in a single transaction."""
    started_at = perf_counter()
    budget = request.content
    try:
        # Any exception inside the block rolls back, so a failing embedder
        # never leaves a document without its chunks.
        async with session.begin():
            existing_id = await session.scalar(
                select(Document.id).where(Document.source_path == request.source_path)
            )
            if existing_id is not None:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "Document already ingested", "document_id": existing_id},
                )

            document = Document(
                source_path=request.source_path,
                document_type=request.document_type,
                metadata_={
                    "budget_id": budget.budget_id,
                    "client_name": budget.client_metadata.name,
                    "sector": budget.client_metadata.sector,
                    "country": budget.client_metadata.country,
                    "project_summary": budget.project_summary,
                    "main_technology": budget.main_technology,
                    "year": budget.year,
                    "total_estimated_hours": budget.total_estimated_hours,
                },
            )
            session.add(document)
            await session.flush()

            chunks = chunker.chunk([budget])
            # The OpenAI client is synchronous; keep it off the event loop.
            embedded_chunks = await run_in_threadpool(embedder.embed, chunks)
            session.add_all(
                Chunk(
                    document_id=document.id,
                    chunk_type=COMPONENT_CHUNK_TYPE,
                    content=chunk.text,
                    embedding=chunk.embedding,
                    metadata_={
                        **chunk.metadata,
                        "chunk_key": chunk.chunk_id,
                        "token_count": chunk.token_count,
                    },
                )
                for chunk in embedded_chunks
            )
    except Exception as exc:  # noqa: BLE001 - provider/DB errors are client-safe at this boundary
        log.error(
            "embedding_ingestion_failed",
            source_path=request.source_path,
            error_type=type(exc).__name__,
            error=str(exc)[:400],
        )
        raise HTTPException(status_code=500, detail="Embedding ingestion failed.") from exc

    return IngestResponse(
        document_id=document.id,
        chunks_created=len(embedded_chunks),
        embedding_dimension=EMBEDDING_DIMENSION,
        ingestion_time_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@lru_cache
def get_reranker() -> CrossEncoderReranker:
    """Process-wide reranker: the model is loaded once, on the first rerank."""
    return CrossEncoderReranker.from_settings()


@search_router.post("/search", response_model=SearchResponse, response_model_exclude_none=True)
async def search_chunks(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedder: OpenAIEmbedder = Depends(get_embedder),
    reranker: CrossEncoderReranker = Depends(get_reranker),
) -> SearchResponse:
    """Return the k best chunks for the query in the requested retrieval mode."""
    settings = get_settings()
    mode = request.mode or settings.SEARCH_MODE
    rerank = settings.RERANK_ENABLED if request.rerank is None else request.rerank
    started_at = perf_counter()
    # Same model as ingestion, otherwise distances are meaningless.
    query_vector = await run_in_threadpool(embedder.embed_one, request.query)
    chunks = await search(
        session,
        request.query,
        query_vector,
        k=request.k,
        mode=mode,
        reranker=reranker if rerank else None,
        recall_k=settings.RETRIEVAL_RECALL_K,
        rrf_k=settings.RRF_K,
    )

    return SearchResponse(
        query=request.query,
        k=request.k,
        search_time_ms=round((perf_counter() - started_at) * 1000, 2),
        results=[
            SearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                distance=chunk.distance,
                metadata=chunk.metadata_,
                rrf_score=chunk.rrf_score,
                rerank_score=chunk.rerank_score,
            )
            for chunk in chunks
        ],
    )
