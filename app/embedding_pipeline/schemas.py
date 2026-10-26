"""Pydantic contracts for the budget embedding pipeline and semantic search."""

from typing import Any, TypeAlias

from pydantic import BaseModel, Field


MetadataValue: TypeAlias = str | int


class ClientMetadata(BaseModel):
    """Client context retained by a normalized historical budget."""

    name: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    country: str = Field(min_length=1)


class BudgetComponent(BaseModel):
    """One estimated unit of work within a budget."""

    component_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tech_stack: list[str] = Field(min_length=1)
    estimated_hours: int = Field(ge=0)
    complexity: str = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)


class Budget(BaseModel):
    """Normalized historical budget accepted by the ingestion boundary."""

    budget_id: str = Field(min_length=1)
    client_metadata: ClientMetadata
    project_summary: str = Field(min_length=1)
    main_technology: str = Field(min_length=1)
    year: int = Field(ge=1900)
    total_estimated_hours: int = Field(ge=0)
    components: list[BudgetComponent] = Field(min_length=1)


class Chunk(BaseModel):
    """A contextualized component ready to submit to an embedding provider."""

    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, MetadataValue]
    token_count: int = Field(ge=0)


class EmbeddedChunk(Chunk):
    """A chunk paired with its provider-generated embedding vector."""

    embedding: list[float]


class IngestRequest(BaseModel):
    """One budget to persist as a document with its embedded chunks."""

    source_path: str = Field(min_length=1)
    document_type: str = Field(min_length=1, max_length=50)
    content: Budget


class IngestResponse(BaseModel):
    """Identifiers and metrics of a persisted ingestion."""

    document_id: int
    chunks_created: int
    embedding_dimension: int
    ingestion_time_ms: float


class SearchRequest(BaseModel):
    """Free-text semantic query over the persisted chunks."""

    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    """One chunk ranked by cosine distance to the query."""

    chunk_id: int
    document_id: int
    chunk_type: str
    content: str
    distance: float
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    """The k nearest chunks and the time spent resolving them."""

    query: str
    k: int
    search_time_ms: float
    results: list[SearchResult]
