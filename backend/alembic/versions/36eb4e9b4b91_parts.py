"""parts

Revision ID: 36eb4e9b4b91
Revises: 9ba250902062
Create Date: 2026-10-02 12:09:33.042160

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36eb4e9b4b91'
down_revision: Union[str, Sequence[str], None] = '9ba250902062'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Written by hand: autogenerate sees a renamed table or column as "drop the old
# one, create a new one", which would delete the text already stored.


def upgrade() -> None:
    """document_pages -> document_parts, so DOCX sections can live beside PDF pages."""
    op.rename_table("document_pages", "document_parts")
    op.execute(
        "ALTER TABLE document_parts RENAME CONSTRAINT document_pages_pkey TO document_parts_pkey"
    )
    op.execute(
        "ALTER TABLE document_parts RENAME CONSTRAINT document_pages_document_id_fkey "
        "TO document_parts_document_id_fkey"
    )
    # The old page number becomes the reading-order position...
    op.alter_column("document_parts", "page_number", new_column_name="position")
    # ...and every existing part is a PDF page, so its page number is its position.
    op.add_column("document_parts", sa.Column("page_number", sa.Integer(), nullable=True))
    op.execute("UPDATE document_parts SET page_number = position")
    op.add_column("document_parts", sa.Column("heading", sa.Text(), nullable=True))
    op.alter_column("documents", "page_count", new_column_name="part_count")


def downgrade() -> None:
    """Back to document_pages. DOCX sections, if any, would be kept as 'pages'."""
    op.alter_column("documents", "part_count", new_column_name="page_count")
    op.drop_column("document_parts", "heading")
    op.drop_column("document_parts", "page_number")
    op.alter_column("document_parts", "position", new_column_name="page_number")
    op.execute(
        "ALTER TABLE document_parts RENAME CONSTRAINT document_parts_document_id_fkey "
        "TO document_pages_document_id_fkey"
    )
    op.execute(
        "ALTER TABLE document_parts RENAME CONSTRAINT document_parts_pkey TO document_pages_pkey"
    )
    op.rename_table("document_parts", "document_pages")
