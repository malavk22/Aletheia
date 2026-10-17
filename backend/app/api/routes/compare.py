import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_workspace_for_member
from app.core.db import get_db
from app.models.workspace import Workspace
from app.schemas.compare import ComparisonRead
from app.services.compare import compare_versions
from app.services.documents import get_document

# Same rule as documents: not signed in -> 401, not a member -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}/compare")


@router.get("", response_model=ComparisonRead)
def compare_documents(
    old: uuid.UUID,
    new: uuid.UUID,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    # GET: comparing only reads what is stored and never calls the AI.
    if old == new:
        raise HTTPException(status_code=422, detail="Choose two different documents")
    documents = [get_document(db, workspace, document_id) for document_id in (old, new)]
    # Both must be in this workspace, so a document is only reached through
    # its own workspace.
    if None in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    if any(document.status != "ready" for document in documents):
        raise HTTPException(
            status_code=409, detail="Documents can be compared once both are processed"
        )
    return compare_versions(db, *documents)
