import uuid

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document import Document
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
