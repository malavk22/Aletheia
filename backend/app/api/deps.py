import uuid

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.ai_errors import too_many
from app.core import rate_limit
from app.core.db import get_db
from app.models.document import Document, DocumentPart
from app.models.user import User
from app.models.workspace import Workspace
from app.services.auth import get_user_for_token
from app.services.documents import get_document
from app.services.workspaces import get_member_workspace

SESSION_COOKIE = "session"


def get_current_user(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    user = get_user_for_token(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def limit_ai_requests(user: User = Depends(get_current_user)) -> None:
    """For routes that call Gemini: at most rate_limit.ai_requests a user, so
    one person can't use up the shared quota."""
    wait = rate_limit.ai_requests.hit(str(user.id))
    if wait is not None:
        raise too_many(wait, "AI requests")


def get_workspace_for_member(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    workspace = get_member_workspace(db, user, workspace_id)
    if workspace is None:
        # 404, not 403: a non-member must not learn that the workspace exists.
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


def get_document_in_workspace(
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
) -> Document:
    # Builds on the workspace check, and the document must belong to that
    # workspace, so it can only be reached through its own workspace.
    document = get_document(db, workspace, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def check_chosen_documents(
    db: Session, workspace: Workspace, document_ids: list[uuid.UUID] | None
) -> list[uuid.UUID] | None:
    """The documents a search is limited to; None means all of them. Every
    chosen id must be a document of this workspace: one from elsewhere gets
    the same 404 as opening it would."""
    if document_ids is None:
        return None
    if not document_ids:
        raise HTTPException(status_code=422, detail="Choose at least one document")
    chosen = set(document_ids)
    found = db.scalars(
        select(Document.id).where(Document.id.in_(chosen), Document.workspace_id == workspace.id)
    ).all()
    if len(found) != len(chosen):
        raise HTTPException(status_code=404, detail="Document not found")
    return list(chosen)


def check_chosen_parts(
    db: Session, document_ids: list[uuid.UUID] | None, part_from: int | None, part_to: int | None
) -> tuple[int, int] | None:
    """The pages or sections (part positions, both included) a search is
    limited to; None means all. Only within one chosen document (already
    checked to be this workspace's): page 3 means something else in each
    document. A missing end means the first or the last part."""
    if part_from is None and part_to is None:
        return None
    if document_ids is None or len(document_ids) != 1:
        raise HTTPException(
            status_code=422, detail="Choose one document to search some of its pages or sections"
        )
    last = db.scalar(select(func.max(DocumentPart.position)).where(DocumentPart.document_id == document_ids[0]))
    # Not `part_from or 1`: 0 is a wrong page, not a missing one.
    first = 1 if part_from is None else part_from
    final = last if part_to is None else part_to
    if last is None or not 1 <= first <= final <= last:
        raise HTTPException(status_code=422, detail="Choose pages or sections that are in the document")
    return first, final
