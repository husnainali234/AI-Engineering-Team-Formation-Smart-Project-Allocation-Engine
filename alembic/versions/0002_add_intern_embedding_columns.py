"""Day 4: add skill_embedding / embedding_updated_at / embedding_source_hash
to interns, for the Sentence-Transformers (all-MiniLM-L6-v2) embedding
pipeline and its change-detection cache.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interns", sa.Column("skill_embedding", sa.JSON(), nullable=True))
    op.add_column("interns", sa.Column("embedding_updated_at", sa.DateTime(), nullable=True))
    op.add_column("interns", sa.Column("embedding_source_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("interns", "embedding_source_hash")
    op.drop_column("interns", "embedding_updated_at")
    op.drop_column("interns", "skill_embedding")
