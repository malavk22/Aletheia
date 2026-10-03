import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    __tablename__ = "documents"

    # Also the file's name on disk: uploads/<workspace_id>/<id>
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    # Kept (as empty) if the uploader's account is deleted, so a shared
    # workspace does not lose its documents.
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # The original name, for display only. Never used as a path.
    filename: Mapped[str] = mapped_column(String(255))
    # Decided by our own check of the file, not by what the sender claimed.
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    # pending: not processed yet; ready: text extracted; failed: see `error`.
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    # Why processing failed, written for people ("This PDF is password-protected").
    error: Mapped[str | None] = mapped_column(String(255))
    # How many parts were stored: pages for a PDF, sections for a DOCX.
    part_count: Mapped[int | None]
    # How many of those parts were read by OCR (scanned pages).
    ocr_part_count: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentPart(Base):
    """One piece of a document's text, with where it came from.

    A PDF is stored page by page (`page_number` set). A DOCX has no fixed
    pages, so it is stored section by section (`heading` set, or empty for text
    before the first heading). Citations later point at this location.
    """

    __tablename__ = "document_parts"

    # The pair is the primary key: a document cannot have two parts at the
    # same position.
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    # Reading order within the document, from 1.
    position: Mapped[int] = mapped_column(primary_key=True)
    # PDF only. Counted from 1, the way people count pages.
    page_number: Mapped[int | None]
    # DOCX only: the heading this text sits under.
    heading: Mapped[str | None] = mapped_column(Text)
    # How the text was obtained: "text" = taken from the file itself (exact);
    # "ocr" = read from a picture of the page (can contain misread words).
    source: Mapped[str] = mapped_column(String(10), server_default="text")
    # The text as extracted (only null characters removed). Empty if the part
    # had no text (for example a blank PDF page).
    text: Mapped[str] = mapped_column(Text)
