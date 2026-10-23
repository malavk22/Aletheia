"""action_done

Revision ID: f88c3c24f494
Revises: 03ec40f112dc
Create Date: 2026-10-23 13:34:18.713823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f88c3c24f494'
down_revision: Union[str, Sequence[str], None] = '03ec40f112dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('document_actions', sa.Column('done_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('document_actions', sa.Column('done_by', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'document_actions_done_by_fkey', 'document_actions', 'users', ['done_by'], ['id'],
        ondelete='SET NULL',
    )
    # Check rules aren't noticed by autogenerate: replaced by hand.
    op.drop_constraint('ck_actions_status', 'document_actions', type_='check')
    op.create_check_constraint(
        'ck_actions_status', 'document_actions',
        "status IN ('suggested', 'confirmed', 'dismissed', 'done')",
    )
    op.drop_constraint('ck_actions_confirmed_has_time', 'document_actions', type_='check')
    op.create_check_constraint(
        'ck_actions_confirmed_has_time', 'document_actions',
        "(status IN ('confirmed', 'done')) = (confirmed_at IS NOT NULL)",
    )
    op.create_check_constraint(
        'ck_actions_done_has_time', 'document_actions', "(status = 'done') = (done_at IS NOT NULL)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Done actions go back to confirmed: the old rules don't know "done".
    op.execute("UPDATE document_actions SET status = 'confirmed' WHERE status = 'done'")
    op.drop_constraint('ck_actions_done_has_time', 'document_actions', type_='check')
    op.drop_constraint('ck_actions_confirmed_has_time', 'document_actions', type_='check')
    op.create_check_constraint(
        'ck_actions_confirmed_has_time', 'document_actions',
        "(status = 'confirmed') = (confirmed_at IS NOT NULL)",
    )
    op.drop_constraint('ck_actions_status', 'document_actions', type_='check')
    op.create_check_constraint(
        'ck_actions_status', 'document_actions', "status IN ('suggested', 'confirmed', 'dismissed')"
    )
    op.drop_constraint('document_actions_done_by_fkey', 'document_actions', type_='foreignkey')
    op.drop_column('document_actions', 'done_by')
    op.drop_column('document_actions', 'done_at')
