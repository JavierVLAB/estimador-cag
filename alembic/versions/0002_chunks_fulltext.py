"""Full-text search on chunks: generated tsvector column and its GIN index.

The corpus is written in English, so stemming and stopwords use the 'english'
text search configuration. The column is GENERATED ... STORED, so existing rows
are filled by Postgres when the column is added and new rows stay in sync.

Revision ID: 0002_chunks_fulltext
Revises: 0001_initial_schema
Create Date: 2026-11-06 00:00:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_chunks_fulltext"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE chunks ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.create_index(
        "ix_chunks_content_tsv", "chunks", ["content_tsv"], postgresql_using="gin"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chunks_content_tsv", table_name="chunks")
    op.drop_column("chunks", "content_tsv")
