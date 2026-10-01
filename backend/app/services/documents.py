import uuid
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.storage import document_path, save_file
from app.documents.validation import detect_content_type, display_name
from app.models.document import Document
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
    )
    db.add(document)
    try:
        db.commit()
    except BaseException:
        # No database row means nothing points at the file, so remove it.
        path.unlink(missing_ok=True)
        raise
    return document


def list_documents(db: Session, workspace: Workspace) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.workspace_id == workspace.id)
            .order_by(Document.created_at.desc())
        )
    )
