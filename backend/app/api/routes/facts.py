import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.ai_errors import ai_failure
from app.api.deps import get_document_in_workspace
from app.core.db import get_db
from app.models.document import Document
from app.qa.llm import LLMError
from app.schemas.facts import FactsRead
from app.services.facts import extract_facts, list_facts

logger = logging.getLogger(__name__)

# Same rule as documents: not signed in -> 401, not a member or no such
# document in this workspace -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}/documents/{document_id}/facts")


@router.get("", response_model=FactsRead)
def read_facts(
    document: Document = Depends(get_document_in_workspace),
    db: Session = Depends(get_db),
):
    # Only what is stored: reading never calls Gemini.
    return {"extracted_at": document.facts_extracted_at, "facts": list_facts(db, document)}


@router.post("", response_model=FactsRead)
def run_extraction(
    document: Document = Depends(get_document_in_workspace),
    db: Session = Depends(get_db),
):
    if document.status != "ready":
        # 409 Conflict: the request is fine, the document isn't in a state
        # where it can be done (still processing, or processing failed).
        raise HTTPException(
            status_code=409, detail="Key facts can be extracted once the document is processed"
        )
    try:
        result = extract_facts(db, document)
    except LLMError as error:
        # Details go to the server log; the person gets a message they can act on.
        logger.exception("Extracting key facts failed")
        raise ai_failure(error, "Couldn't extract key facts")
    return {
        "extracted_at": document.facts_extracted_at,
        "facts": list_facts(db, document),
        "dropped": result["dropped"],
    }
