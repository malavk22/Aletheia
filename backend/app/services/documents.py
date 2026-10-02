import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.extraction import ExtractionFailed, extract_pdf_pages
from app.documents.storage import document_path, save_file
from app.documents.validation import PDF, detect_content_type, display_name
from app.models.document import Document, DocumentPage
from app.models.user import User
from app.models.workspace import Workspace


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
        status="pending",
    )
    pages = _extract_text(document, path)
    db.add(document)
    try:
        # flush sends the document row first, so the pages can point at it.
        db.flush()
        db.add_all(pages)
        db.commit()
    except BaseException:
        # No database row means nothing points at the file, so remove it.
        path.unlink(missing_ok=True)
        raise
    return document


def _extract_text(document: Document, path: Path) -> list[DocumentPage]:
    """Set the document's status and return its pages (empty if none).

    A failure here never fails the upload: the file is kept and the reason is
    stored, so it can be processed again later (for example with OCR).
    """
    if document.content_type != PDF:
        return []  # DOCX gets its own extraction step; it stays "pending".

    try:
        with path.open("rb") as stored:
            texts = extract_pdf_pages(stored)
    except ExtractionFailed as failure:
        document.status = "failed"
        document.error = str(failure)
        return []

    document.status = "ready"
    document.page_count = len(texts)
    return [
        DocumentPage(document_id=document.id, page_number=number, text=text)
        for number, text in enumerate(texts, start=1)
    ]


def list_pages(db: Session, document: Document) -> list[DocumentPage]:
    return list(
        db.scalars(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
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
