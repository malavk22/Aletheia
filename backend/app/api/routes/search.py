import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import check_chosen_documents, check_chosen_parts, get_workspace_for_member
from app.core.db import get_db
from app.models.workspace import Workspace
from app.schemas.search import SearchResult
from app.services.search import keyword_search, semantic_search

# Same rule as documents: not signed in -> 401, not a member -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}/search")


@router.get("", response_model=list[SearchResult])
def search(
    q: str = Query(max_length=500),
    # semantic: by meaning (the default); keyword: by the exact words.
    mode: Literal["semantic", "keyword"] = "semantic",
    limit: int = Query(10, ge=1, le=50),
    # Repeat to choose several: ?document_id=…&document_id=…; left out, all.
    document_id: list[uuid.UUID] | None = Query(None, max_length=100),
    # With one document chosen: only these of its pages or sections.
    part_from: int | None = None,
    part_to: int | None = None,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    if not q.strip():
        raise HTTPException(status_code=422, detail="Type something to search for")
    document_ids = check_chosen_documents(db, workspace, document_id)
    parts = check_chosen_parts(db, document_ids, part_from, part_to)
    run = keyword_search if mode == "keyword" else semantic_search
    return run(db, workspace, q.strip(), limit, document_ids, parts)
