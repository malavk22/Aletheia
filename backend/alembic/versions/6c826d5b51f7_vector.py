"""vector

Revision ID: 6c826d5b51f7
Revises: d51d2edbc179
Create Date: 2026-10-03 19:22:34.760651

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c826d5b51f7'
down_revision: Union[str, Sequence[str], None] = 'd51d2edbc179'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Turns on pgvector in this database: adds the "vector" column type and
    # the operators that measure how close two vectors are.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS vector")
