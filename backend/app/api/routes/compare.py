import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.ai_errors import ai_failure
from app.api.deps import get_workspace_for_member, limit_ai_requests
from app.core.db import get_db
from app.models.document import Document
from app.models.workspace import Workspace
from app.qa.llm import LLMError
from app.schemas.compare import ComparisonRead, ConflictsRead, ConflictsRequest
from app.services.compare import compare_versions
from app.services.conflicts import find_conflicts
from app.services.documents import get_document

logger = logging.getLogger(__name__)

# Same rule as documents: not signed in -> 401, not a member -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}/compare")


def _two_documents(db: Session, workspace: Workspace, first: uuid.UUID, second: uuid.UUID):
    """Both documents, if they can be compared: different, in this
    workspace, and processed."""
    if first == second:
        raise HTTPException(status_code=422, detail="Choose two different documents")
    documents = [get_document(db, workspace, document_id) for document_id in (first, second)]
    # Both must be in this workspace, so a document is only reached through
    # its own workspace.
    if None in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    if any(document.status != "ready" for document in documents):
        raise HTTPException(
            status_code=409, detail="Documents can be compared once both are processed"
        )
    return documents


@router.get("", response_model=ComparisonRead)
def compare_documents(
    old: uuid.UUID,
    new: uuid.UUID,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    # GET: comparing only reads what is stored and never calls the AI.
    return compare_versions(db, *_two_documents(db, workspace, old, new))


@router.post("/conflicts", response_model=ConflictsRead)
def check_conflicts(
    request: ConflictsRequest,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
    _limit: None = Depends(limit_ai_requests),
):
    # POST: this one sends passages to Gemini.
    documents: list[Document] = _two_documents(
        db, workspace, request.document_a, request.document_b
    )
    try:
        result = find_conflicts(db, *documents)
    except LLMError as error:
        # Details go to the server log; the person gets a message they can act on.
        logger.exception("Checking for conflicts failed")
        raise ai_failure(error, "Couldn't check for conflicts")
    return {
        "potential_conflicts": result["conflicts"],
        "checked_pairs": result["checked_pairs"],
        "dropped": result["dropped"],
    }
