"""Stateless HTTP ingestion boundary for structural budget embeddings."""

import structlog
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_openai_client
from app.embedding_pipeline.chunker import JSONStructuralChunker
from app.embedding_pipeline.embedder import OpenAIEmbedder
from app.embedding_pipeline.schemas import IngestRequest, IngestResponse

log = structlog.get_logger()

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


def get_embedder() -> OpenAIEmbedder:
    """Build the adapter at request time so endpoint tests can replace it."""
    return OpenAIEmbedder(get_openai_client())


def get_chunker() -> JSONStructuralChunker:
    """Build the stateless structural chunker for one ingestion request."""
    return JSONStructuralChunker()


@router.post("/ingest", response_model=IngestResponse)
def ingest_budgets(
    request: IngestRequest,
    chunker: JSONStructuralChunker = Depends(get_chunker),
    embedder: OpenAIEmbedder = Depends(get_embedder),
) -> IngestResponse:
    """Chunk and embed a submitted budget set without persisting any output."""
    try:
        chunks = chunker.chunk(request.budgets)
        embedded_chunks = embedder.embed(chunks)
    except Exception as exc:  # noqa: BLE001 - provider errors are client-safe at this boundary
        log.error(
            "embedding_ingestion_failed",
            error_type=type(exc).__name__,
            error=str(exc)[:400],
        )
        raise HTTPException(status_code=500, detail="Embedding ingestion failed.") from exc

    total_tokens = sum(chunk.token_count for chunk in chunks)
    return IngestResponse(
        chunks=embedded_chunks,
        stats={
            "total_budgets": len(request.budgets),
            "total_chunks": len(chunks),
            "total_tokens": total_tokens,
            "estimated_cost_usd": OpenAIEmbedder.estimate_cost_usd(total_tokens),
        },
    )
