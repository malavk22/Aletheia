from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_for_member
from app.core.db import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead
from app.services.workspaces import (
    create_workspace,
    delete_workspace,
    is_owner,
    list_workspaces,
)

router = APIRouter(prefix="/workspaces")


@router.post("", response_model=WorkspaceRead, status_code=201)
def create(
    data: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_workspace(db, user, data.name)


@router.get("", response_model=list[WorkspaceRead])
def list_mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_workspaces(db, user)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_one(workspace: Workspace = Depends(get_workspace_for_member)):
    return workspace


@router.delete("/{workspace_id}", status_code=204)
def delete(
    workspace: Workspace = Depends(get_workspace_for_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Non-members already got 404 from get_workspace_for_member. A member who
    # is not the owner knows the workspace exists, so 403 hides nothing.
    if not is_owner(db, user, workspace):
        raise HTTPException(
            status_code=403, detail="Only the owner can delete this workspace"
        )
    delete_workspace(db, workspace)
