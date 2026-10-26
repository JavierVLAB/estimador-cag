"""SQLAlchemy models for persisted budget documents and their embedded chunks."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSION = 1536


class Base(DeclarativeBase):
    """Declarative base whose metadata Alembic compares against the database."""


class Document(Base):
    """One ingested source document, such as a historical budget."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # "metadata" is reserved by the declarative API, so the attribute gets a suffix.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=False
    )


class Chunk(Base):
    """One embedded fragment of a document."""

    __tablename__ = "chunks"
    # GIN lets metadata filters use an index without migrating the schema.
    # No vector index on purpose: the live session measures the sequential scan first.
    __table_args__ = (Index("ix_chunks_metadata_gin", "metadata", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
