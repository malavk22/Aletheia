import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_document_in_workspace, get_workspace_for_member
from app.core.db import get_db
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.qa.llm import LLMError
from app.schemas.actions import ActionRead, ActionUpdate, DocumentActionsRead
from app.services.actions import extract_actions, get_action, list_actions, update_action

logger = logging.getLogger(__name__)

# Same rule as documents: not signed in -> 401, not a member or no such
# document or action in this workspace -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}")


@router.get("/documents/{document_id}/actions", response_model=DocumentActionsRead)
def read_document_actions(
    document: Document = Depends(get_document_in_workspace),
    db: Session = Depends(get_db),
):
    # Only what is stored: reading never calls Gemini.
    return {
        "extracted_at": document.actions_extracted_at,
        "actions": list_actions(db, document_id=document.id),
    }


@router.post("/documents/{document_id}/actions", response_model=DocumentActionsRead)
def run_extraction(
    document: Document = Depends(get_document_in_workspace),
    db: Session = Depends(get_db),
):
    if document.status != "ready":
        raise HTTPException(
            status_code=409, detail="Actions can be found once the document is processed"
        )
    try:
        result = extract_actions(db, document)
    except LLMError:
        # Details go to the server log; the person gets a message they can act on.
        logger.exception("Extracting actions failed")
        raise HTTPException(
            status_code=503, detail="Couldn't find actions right now. Try again in a minute."
        )
    return {
        "extracted_at": document.actions_extracted_at,
        "actions": list_actions(db, document_id=document.id),
        "dropped": result["dropped"],
    }


@router.get("/actions", response_model=list[ActionRead])
def read_workspace_actions(
    # Repeat it for several: ?status=confirmed&status=done; none given: all.
    status: list[Literal["suggested", "confirmed", "dismissed", "done"]] = Query(default=[]),
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    # For the timeline and the upcoming list: confirmed and done.
    return list_actions(db, workspace_id=workspace.id, statuses=status)


@router.patch("/actions/{action_id}", response_model=ActionRead)
def change_action(
    action_id: uuid.UUID,
    request: ActionUpdate,
    workspace: Workspace = Depends(get_workspace_for_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    action = get_action(db, workspace.id, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    # Only the fields the person sent: a missing due_date means "keep it",
    # while due_date: null means "clear it".
    changes = request.model_dump(include=request.model_fields_set)
    if changes.get("status") is None:
        changes.pop("status", None)
    try:
        update_action(db, action, user.id, changes)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    [updated] = [
        item for item in list_actions(db, document_id=action.document_id) if item["id"] == action.id
    ]
    return updated
