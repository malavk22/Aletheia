import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership


def create_workspace(db: Session, user: User, name: str) -> Workspace:
    workspace = Workspace(name=name)
    db.add(workspace)
    # flush sends the INSERT so workspace.id exists; nothing is saved until commit,
    # so the workspace and its owner membership are saved together or not at all.
    db.flush()
    db.add(
        WorkspaceMembership(user_id=user.id, workspace_id=workspace.id, role="owner")
    )
    db.commit()
    return workspace


def _workspaces_of(user: User):
    return (
        select(Workspace)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user.id)
    )


def list_workspaces(db: Session, user: User) -> list[Workspace]:
    return list(db.scalars(_workspaces_of(user).order_by(Workspace.created_at)))


def get_member_workspace(
    db: Session, user: User, workspace_id: uuid.UUID
) -> Workspace | None:
    return db.scalar(_workspaces_of(user).where(Workspace.id == workspace_id))
