# app/api/routes/application_document.py

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user
from app.crud import application_document as crud_doc
from app.db.session import get_db
from app.models.user import User
from app.schemas.application_document import (
    ApplicationDocumentListResponse,
    ApplicationDocumentRead,
    DeleteDocumentResponse,
    UploadDocumentResponse,
)

from app.services.google_drive import (
    delete_file_from_drive,
    get_or_create_application_folder,
    upload_file_to_drive,
)

router = APIRouter(
    prefix="/api/application-documents",
    tags=["Application Documents"],
    dependencies=[Depends(get_current_active_user)],
)

# ── 5 MB hard limit ──────────────────────────────────────────────────
MAX_FILE_SIZE = 5 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post("/upload", response_model=UploadDocumentResponse, status_code=201)
async def upload_document(
    main_db_id: int = Form(...),
    db_entry_type: str = Form(...),
    db_dtn: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a supporting document to Google Drive and record it in the DB."""

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{file.content_type}' is not allowed. "
                   f"Accepted: PDF, JPG, PNG, GIF, WEBP, DOC, DOCX, XLS, XLSX.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the 5 MB limit.")

    # ── Get or create yung nested folder: db_entry_type / db_dtn ────
    folder_id = crud_doc.get_existing_folder_id(db, db_entry_type, db_dtn)
    if not folder_id:
        try:
            folder_id = get_or_create_application_folder(db_entry_type, db_dtn)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to prepare Drive folder: {exc}",
            )

    # ── Upload to Google Drive ───────────────────────────────────────
    try:
        drive_result = upload_file_to_drive(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            folder_id=folder_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Google Drive upload failed: {exc}",
        )

    from app.schemas.application_document import ApplicationDocumentCreate

    payload = ApplicationDocumentCreate(
        main_db_id=main_db_id,
        db_entry_type=db_entry_type,
        db_dtn=db_dtn,
        drive_file_id=drive_result["file_id"],
        drive_file_url=drive_result["file_url"],
        drive_folder_id=drive_result.get("folder_id") or folder_id,
        original_filename=file.filename,
        mime_type=file.content_type,
        file_size_bytes=len(file_bytes),
        uploaded_by_user_id=current_user.id,
        uploaded_by_user_name=current_user.username,
    )
    doc = crud_doc.create_document(db, payload)

    return UploadDocumentResponse(
        id=doc.id,
        drive_file_id=doc.drive_file_id,
        drive_file_url=doc.drive_file_url,
        original_filename=doc.original_filename,
        file_size_bytes=doc.file_size_bytes,
    )


@router.get("/{main_db_id}", response_model=ApplicationDocumentListResponse)
def list_documents(
    main_db_id: int,
    db: Session = Depends(get_db),
):
    """Return all non-deleted documents for a given application."""
    docs = crud_doc.get_documents_by_main_db_id(db, main_db_id)
    return ApplicationDocumentListResponse(data=docs, total=len(docs))


@router.delete("/{document_id}", response_model=DeleteDocumentResponse)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Soft-delete the DB record and permanently delete from Google Drive.
    """
    doc = crud_doc.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete from Drive first (non-fatal if already gone)
    delete_file_from_drive(doc.drive_file_id)

    # Soft-delete in DB
    crud_doc.soft_delete_document(
        db, document_id, deleted_by=current_user.username
    )

    return DeleteDocumentResponse(message="Document deleted successfully.")