from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_document_in_workspace,
    get_workspace_for_member,
)
from app.core.config import settings
from app.core.db import get_db
from app.documents.storage import FileTooLarge, document_path
from app.documents.validation import PDF, UnsupportedFileType
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.document import DocumentPartRead, DocumentRead
from app.services.documents import (
    delete_document,
    list_documents,
    list_parts,
    upload_document,
)

# Every route here sits under a workspace, so each one depends on
# get_workspace_for_member: not signed in -> 401, not a member -> 404.
# Routes for one document use get_document_in_workspace, which adds: the
# document must exist in that workspace -> otherwise 404.
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


@router.get("/{document_id}", response_model=DocumentRead)
def get_one(document: Document = Depends(get_document_in_workspace)):
    return document


@router.delete("/{document_id}", status_code=204)
def delete(
    document: Document = Depends(get_document_in_workspace),
    db: Session = Depends(get_db),
):
    delete_document(db, document)


@router.get("/{document_id}/parts", response_model=list[DocumentPartRead])
def parts(
    document: Document = Depends(get_document_in_workspace),
    db: Session = Depends(get_db),
):
    return list_parts(db, document)


@router.get("/{document_id}/file")
def original_file(document: Document = Depends(get_document_in_workspace)):
    path = document_path(document.workspace_id, document.id)
    if not path.is_file():
        # The row exists but the file is gone (for example removed by hand).
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        # The type our own upload check decided, never a guess from the name.
        media_type=document.content_type,
        filename=document.filename,
        # PDFs open in the browser; Word files download (browsers can't show them).
        content_disposition_type=(
            "inline" if document.content_type == PDF else "attachment"
        ),
        # Tells the browser not to second-guess that type (for example to treat
        # a file as a web page and run scripts in it).
        headers={"X-Content-Type-Options": "nosniff"},
    )
