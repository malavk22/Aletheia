import logging
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.documents.extraction import (
    ExtractionFailed,
    extract_docx_sections,
    extract_pdf_pages,
)
from app.documents.storage import document_path, save_file
from app.documents.validation import PDF, detect_content_type, display_name
from app.models.document import Document, DocumentPart
from app.models.user import User
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)

INTERRUPTED = "Processing was interrupted. Please upload it again."
UNEXPECTED_FAILURE = "Processing failed unexpectedly. Please upload it again."


def upload_document(
    db: Session, workspace: Workspace, user: User, filename: str, file: BinaryIO
) -> Document:
    # Check first, so a rejected file is never written to disk.
    content_type = detect_content_type(filename, file)

    document_id = uuid.uuid4()
    path = document_path(workspace.id, document_id)
    size = save_file(file, path)

    document = Document(
        id=document_id,
        workspace_id=workspace.id,
        uploaded_by=user.id,
        filename=display_name(filename)[:255],
        content_type=content_type,
        size_bytes=size,
        # The text is extracted afterwards, by process_document, so the
        # upload can answer straight away.
        status="processing",
    )
    db.add(document)
    try:
        db.commit()
    except BaseException:
        # No database row means nothing points at the file, so remove it.
        path.unlink(missing_ok=True)
        raise
    return document


@contextmanager
def open_session():
    """A database session of the job's own. Background jobs run after the
    request's session has been closed, so they cannot borrow it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def process_document(document_id: uuid.UUID) -> None:
    """Extract a document's text. Runs in the background, after the upload has
    already answered, so slow work (long PDFs, later OCR) never makes the
    person wait."""
    with open_session() as db:
        document = db.get(Document, document_id)
        if document is None:
            return  # deleted before its turn came; nothing to do
        try:
            path = document_path(document.workspace_id, document.id)
            parts = _extract_text(document, path)
            db.add_all(parts)
            db.commit()
        except Exception:
            # Something unexpected (a bug, or the document was deleted while
            # being processed). Never leave it stuck on "processing".
            db.rollback()
            logger.exception("Processing document %s failed", document_id)
            _mark_failed(db, document_id, UNEXPECTED_FAILURE)


def fail_interrupted_documents(db: Session) -> None:
    """Run when the server starts. A document still "processing" then was cut
    off by the server stopping; its job will never finish, so say so."""
    db.execute(
        update(Document)
        .where(Document.status == "processing")
        .values(status="failed", error=INTERRUPTED)
    )
    db.commit()


def _mark_failed(db: Session, document_id: uuid.UUID, reason: str) -> None:
    # An update by id: if the document no longer exists it changes nothing.
    db.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status="failed", error=reason)
    )
    db.commit()


def _extract_text(document: Document, path: Path) -> list[DocumentPart]:
    """Set the document's status and return its parts (empty if none).

    A PDF becomes one part per page; a DOCX one part per section. A failure
    here never fails the upload: the file is kept and the reason is stored, so
    it can be processed again later (for example with OCR).
    """
    try:
        with path.open("rb") as stored:
            if document.content_type == PDF:
                parts = [
                    DocumentPart(
                        position=number, page_number=number, text=text, source=source
                    )
                    for number, (text, source) in enumerate(
                        extract_pdf_pages(stored), start=1
                    )
                ]
            else:
                parts = [
                    DocumentPart(
                        position=number, heading=heading, text=text, source="text"
                    )
                    for number, (heading, text) in enumerate(
                        extract_docx_sections(stored), start=1
                    )
                ]
    except ExtractionFailed as failure:
        document.status = "failed"
        document.error = str(failure)
        return []

    for part in parts:
        part.document_id = document.id
    document.status = "ready"
    document.part_count = len(parts)
    document.ocr_part_count = sum(1 for part in parts if part.source == "ocr")
    return parts


def list_parts(db: Session, document: Document) -> list[DocumentPart]:
    return list(
        db.scalars(
            select(DocumentPart)
            .where(DocumentPart.document_id == document.id)
            .order_by(DocumentPart.position)
        )
    )


def list_documents(db: Session, workspace: Workspace) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.workspace_id == workspace.id)
            .order_by(Document.created_at.desc())
        )
    )


def get_document(
    db: Session, workspace: Workspace, document_id: uuid.UUID
) -> Document | None:
    # Matching on the workspace too means a document can only be reached
    # through the workspace it belongs to.
    return db.scalar(
        select(Document).where(
            Document.id == document_id, Document.workspace_id == workspace.id
        )
    )


def delete_document(db: Session, document: Document) -> None:
    path = document_path(document.workspace_id, document.id)
    # Row first, file second: if removing the file failed we would only leave
    # an unused file behind, never a row pointing at a missing file.
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
