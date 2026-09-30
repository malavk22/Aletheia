from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_for_member
from app.core.config import settings
from app.core.db import get_db
from app.documents.storage import FileTooLarge
from app.documents.validation import UnsupportedFileType
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentRead
from app.services.documents import list_documents, upload_document

# Every route here sits under a workspace, so each one depends on
# get_workspace_for_member: not signed in -> 401, not a member -> 404.
router = APIRouter(prefix="/workspaces/{workspace_id}/documents")


@router.post("", response_model=DocumentRead, status_code=201)
def upload(
    file: UploadFile,
    workspace: Workspace = Depends(get_workspace_for_member),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return upload_document(db, workspace, user, file.filename or "", file.file)
    except UnsupportedFileType:
        raise HTTPException(status_code=415, detail="Only PDF and DOCX files are supported")
    except FileTooLarge:
        raise HTTPException(
            status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB"
        )


@router.get("", response_model=list[DocumentRead])
def list_for_workspace(
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    return list_documents(db, workspace)
