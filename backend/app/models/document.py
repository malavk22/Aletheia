import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    func,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.documents.embeddings import DIMENSIONS


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
    # When key facts were last extracted (V0.5). Empty: never, which is
    # different from "extracted, none found".
    facts_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When actions were last extracted (V0.7). Empty: never.
    actions_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class DocumentChunk(Base):
    """A small piece of one part's text: the unit that search finds.

    A chunk never spans two parts, so it always has exactly one location: the
    page or section of its part. That is what a search result (and later a
    citation) points at.
    """

    __tablename__ = "document_chunks"
    # The chunk's part, found by (document, part position). Deleting the part
    # (or its document) deletes its chunks.
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "part_position"],
            ["document_parts.document_id", "document_parts.position"],
            ondelete="CASCADE",
        ),
        # Lets keyword search find matching chunks without reading every one.
        Index("ix_document_chunks_search_words", "search_words", postgresql_using="gin"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # Reading order within the whole document, from 1.
    position: Mapped[int] = mapped_column(primary_key=True)
    # Which part (page or section) the chunk was cut from.
    part_position: Mapped[int]
    # Whitespace tidied to single spaces; otherwise the part's own words.
    text: Mapped[str] = mapped_column(Text)
    # The chunk's meaning as numbers: chunks about similar things have
    # vectors that point in similar directions. Empty only for chunks made
    # before embeddings existed, until the backfill fills them in.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIMENSIONS))
    # The chunk's words for keyword search, reduced to their stems ("terminated"
    # and "termination" both become "termin") with common words like "the"
    # left out. PostgreSQL fills this in itself whenever `text` is written.
    search_words: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )


class DocumentFact(Base):
    """A fact pulled out of a document by the AI (V0.5): a person, an
    organization, a date, an amount or a requirement, with the exact sentence
    it came from and that sentence's page or section.

    Only facts whose quote was found in the part they name are stored, so
    every fact can be checked against the document itself.
    """

    __tablename__ = "document_facts"
    # The fact's part, found by (document, part position). Deleting the part
    # (or its document) deletes its facts.
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "part_position"],
            ["document_parts.document_id", "document_parts.position"],
            ondelete="CASCADE",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # The order the facts were extracted in, from 1.
    position: Mapped[int] = mapped_column(primary_key=True)
    # person, organization, date, amount or requirement.
    kind: Mapped[str] = mapped_column(String(20))
    # The fact in short: "Mr. Hirenkumar Mer", "2,000 dollars", "1 January 2026".
    value: Mapped[str] = mapped_column(Text)
    # Dates only: the same date as YYYY-MM-DD, so dates can be sorted and
    # compared. Empty when the document gives no full date ("next spring").
    normalized: Mapped[str | None] = mapped_column(String(10))
    # What the fact is about: "project guide", "monthly rent", "lease start".
    about: Mapped[str | None] = mapped_column(Text)
    # The document's own words the fact comes from, as found in the part.
    quote: Mapped[str] = mapped_column(Text)
    # Which part (page or section) the quote is in.
    part_position: Mapped[int]


class DocumentAction(Base):
    """Something someone must do, found in a document by the AI (V0.7): a
    deadline or a task, with the exact sentence it came from and that
    sentence's page or section.

    Kept apart from facts: facts are read-only and replaced on every
    extraction, while actions are confirmed, edited or dismissed by a person.
    An action starts as a suggestion and only counts once a person confirms it.

    The rules below are checked by the database itself, so no code path can
    break them, above all: a due date never comes from the document unless
    the document gives a full date.
    """

    __tablename__ = "document_actions"
    __table_args__ = (
        # The action's part, found by (document, part position). Deleting the
        # part (or its document) deletes its actions.
        ForeignKeyConstraint(
            ["document_id", "part_position"],
            ["document_parts.document_id", "document_parts.position"],
            ondelete="CASCADE",
        ),
        # A document's actions are read (and deleted) together.
        Index("ix_document_actions_document_id", "document_id"),
        CheckConstraint("kind IN ('deadline', 'task')", name="ck_actions_kind"),
        CheckConstraint("due_kind IN ('exact', 'relative', 'none')", name="ck_actions_due_kind"),
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="ck_actions_confidence"),
        CheckConstraint("status IN ('suggested', 'confirmed', 'dismissed')", name="ck_actions_status"),
        # A date always says where it came from, and a source always has a date.
        CheckConstraint(
            "(due_date IS NULL) = (due_date_source IS NULL)", name="ck_actions_due_date_has_source"
        ),
        # Never an invented date: the document only gives a date when it
        # states one in full. A relative deadline gets a date from a person.
        CheckConstraint(
            "due_date_source <> 'document' OR due_kind = 'exact'", name="ck_actions_document_date_is_exact"
        ),
        CheckConstraint("due_kind <> 'exact' OR due_date IS NOT NULL", name="ck_actions_exact_has_date"),
        # A deadline as written ("by 15 March 2026", "within 30 days of
        # leaving") is kept whenever there is one.
        CheckConstraint("due_kind = 'none' OR due_text IS NOT NULL", name="ck_actions_due_has_text"),
        CheckConstraint(
            "(status = 'confirmed') = (confirmed_at IS NOT NULL)", name="ck_actions_confirmed_has_time"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID]
    # Which part (page or section) the quote is in.
    part_position: Mapped[int]
    # deadline (something due by a time) or task (something to do).
    kind: Mapped[str] = mapped_column(String(20))
    # What has to be done, in short: "Give notice before leaving".
    title: Mapped[str] = mapped_column(Text)
    # Who has to do it, as the document says: "the tenant". Empty if not said.
    responsible: Mapped[str | None] = mapped_column(Text)
    # What the document says about when:
    # exact: a full date ("15 March 2026"); relative: tied to something else
    # or incomplete ("within 30 days of leaving", "by 15 March"); none.
    due_kind: Mapped[str] = mapped_column(String(10))
    # The "when" in the document's own words. Empty for "none".
    due_text: Mapped[str | None] = mapped_column(Text)
    # The due date, if known; empty for relative deadlines until a person
    # sets one.
    due_date: Mapped[date | None] = mapped_column(Date)
    # Where the date came from: "document" (exact deadlines only) or "person".
    due_date_source: Mapped[str | None] = mapped_column(String(10))
    # The document's own words the action comes from, as found in the part.
    quote: Mapped[str] = mapped_column(Text)
    # How much to trust the suggestion: high, medium or low, worked out by
    # rules from the evidence, not asked from the AI.
    confidence: Mapped[str] = mapped_column(String(10))
    # suggested (found by the AI, not yet counted), confirmed or dismissed.
    status: Mapped[str] = mapped_column(String(20), server_default="suggested")
    # When and by whom it was confirmed. The person is kept as empty if
    # their account is deleted.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
