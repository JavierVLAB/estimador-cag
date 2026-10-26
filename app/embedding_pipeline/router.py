"""HTTP boundary that persists budget embeddings in pgvector and searches them."""

from time import perf_counter

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


@search_router.post("/search", response_model=SearchResponse)
async def search_chunks(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedder: OpenAIEmbedder = Depends(get_embedder),
) -> SearchResponse:
    """Return the k chunks closest to the query by cosine distance."""
    started_at = perf_counter()
    # Same model as ingestion, otherwise distances are meaningless.
    query_vector = await run_in_threadpool(embedder.embed_one, request.query)

    # `<=>` (cosine) must match the operator class of the index created live
    # (vector_cosine_ops); otherwise Postgres silently falls back to a seq scan.
    distance = Chunk.embedding.cosine_distance(query_vector)
    stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.chunk_type,
            Chunk.content,
            Chunk.metadata_,
            distance.label("distance"),
        )
        .order_by(distance)
        .limit(request.k)
    )
    rows = (await session.execute(stmt)).all()

    return SearchResponse(
        query=request.query,
        k=request.k,
        search_time_ms=round((perf_counter() - started_at) * 1000, 2),
        results=[
            SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                chunk_type=row.chunk_type,
                content=row.content,
                distance=row.distance,
                metadata=row.metadata_,
            )
            for row in rows
        ],
    )
