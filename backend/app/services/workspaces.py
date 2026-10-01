import shutil
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.storage import workspace_folder
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


def is_owner(db: Session, user: User, workspace: Workspace) -> bool:
    role = db.scalar(
        select(WorkspaceMembership.role).where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.workspace_id == workspace.id,
        )
    )
    return role == "owner"


def delete_workspace(db: Session, workspace: Workspace) -> None:
    folder = workspace_folder(workspace.id)
    # The database removes the workspace's memberships and documents itself
    # (ON DELETE CASCADE). Files on disk are ours to remove, and only after the
    # rows are gone: at worst a folder is left behind, never a half-deleted
    # workspace.
    db.delete(workspace)
    db.commit()
    shutil.rmtree(folder, ignore_errors=True)
