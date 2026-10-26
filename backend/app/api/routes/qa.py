import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.ai_errors import ai_failure
from app.api.deps import (
    check_chosen_documents,
    check_chosen_parts,
    get_workspace_for_member,
    limit_ai_requests,
)
from app.core.db import get_db
from app.models.workspace import Workspace
from app.qa.llm import LLMError
from app.schemas.qa import AskRequest, AskResponse
from app.services.qa import answer_question

logger = logging.getLogger(__name__)

# Same rule as documents and search: not signed in -> 401, not a member -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}/ask")


# POST, not GET: a question is closer to a message than to an address, and
# it stays out of URLs, browser history and server logs.
@router.post("", response_model=AskResponse)
def ask(
    body: AskRequest,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
    _limit: None = Depends(limit_ai_requests),
):
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Type a question to ask")
    document_ids = check_chosen_documents(db, workspace, body.document_ids)
    parts = check_chosen_parts(db, document_ids, body.part_from, body.part_to)
    try:
        return answer_question(db, workspace, question, document_ids, parts)
    except LLMError as error:
        # The details (which may name the model or quote Google's reply) go
        # to the server log; the person gets a message they can act on.
        logger.exception("Answering a question failed")
        raise ai_failure(error, "Couldn't write an answer")
