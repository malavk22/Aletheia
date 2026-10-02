import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_workspace_for_member
from app.core.config import settings
from app.core.db import get_db
from app.documents.storage import FileTooLarge
from app.documents.validation import UnsupportedFileType
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentPartRead, DocumentRead
from app.services.documents import (
    delete_document,
    get_document,
    list_documents,
    list_parts,
    upload_document,
)

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


@router.delete("/{document_id}", status_code=204)
def delete(
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    document = get_document(db, workspace, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_document(db, document)


@router.get("/{document_id}/parts", response_model=list[DocumentPartRead])
def parts(
    document_id: uuid.UUID,
    workspace: Workspace = Depends(get_workspace_for_member),
    db: Session = Depends(get_db),
):
    document = get_document(db, workspace, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return list_parts(db, document)
