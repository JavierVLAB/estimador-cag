"""Pydantic contracts for the in-memory budget embedding pipeline."""

from typing import TypeAlias

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
    """Input body for the stateless embedding ingestion endpoint."""

    budgets: list[Budget] = Field(min_length=1)


class IngestResponse(BaseModel):
    """Embedded chunks and request-scoped aggregate statistics."""

    chunks: list[EmbeddedChunk]
    stats: dict[str, int | float]
