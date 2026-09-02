from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import Annotated

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.crud import cpr_app_document as crud_doc
from app.schemas.cpr_app_document import (
    CPRAppDocumentCreate,
    CPRAppDocumentListResponse,
    CPRAppDocumentUploadResponse,
    CPRAppDocumentDeleteResponse,
)
from app.services.google_drive import (
    delete_file_from_drive,
    find_file_in_folder,
    folder_exists,
    get_or_create_folder_path,
    upload_file_to_drive,
)

router = APIRouter(
    prefix="/api/cpr-app-documents",
    tags=["CPR Application Documents"],
    dependencies=[Depends(get_current_active_user)],
)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB

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

VALID_GROUPS = {"technical", "general"}


def _build_folder_path(
    reference_no: str,
    requirement_group: str,
    requirement_code: str,
    category_code: str | None,
) -> str:
    if requirement_group == "technical":
        parts = ["Input_Documents", "Technical_Req", category_code, requirement_code]
    else:
        parts = ["Input_Documents", "General_Req", requirement_code]
    return get_or_create_folder_path("eApplication", reference_no, parts)


@router.post("/upload", response_model=CPRAppDocumentUploadResponse, status_code=201)
async def upload_document(
    application_uuid: Annotated[str, Form(...)],
    reference_no: Annotated[str, Form(...)],
    application_type: Annotated[str, Form(...)],
    requirement_group: Annotated[str, Form(...)],
    requirement_code: Annotated[str, Form(...)],
    file: Annotated[UploadFile, File(...)],
    category_code: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a single MiV-N (or other application type) requirement document to
    Google Drive and record it against the application."""

    requirement_group = requirement_group.strip().lower()
    if requirement_group not in VALID_GROUPS:
        raise HTTPException(
            status_code=422,
            detail="requirement_group must be 'technical' or 'general'.",
        )

    if requirement_group == "technical" and not (
        category_code and category_code.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="category_code is required when requirement_group is 'technical'.",
        )
    if requirement_group == "general":
        category_code = None  # laging null para consistent, kahit may ipasa

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"File type '{file.content_type}' is not allowed.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the 200 MB limit.")

    # ── Resolve (or create) the Drive folder ──────────────────────────
    candidate_id = crud_doc.get_existing_folder_id(
        db, application_uuid, requirement_group, category_code, requirement_code
    )
    if candidate_id and folder_exists(candidate_id):
        folder_id = candidate_id
    else:
        try:
            folder_id = _build_folder_path(
                reference_no, requirement_group, requirement_code, category_code
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Failed to prepare Drive folder: {exc}"
            )

    # ── Overwrite-if-same-name detection ──────────────────────────────
    existing_doc = crud_doc.get_existing_document_by_name(
        db,
        application_uuid,
        requirement_group,
        category_code,
        requirement_code,
        file.filename,
    )
    existing_drive_file_id = find_file_in_folder(file.filename, folder_id)

    try:
        drive_result = upload_file_to_drive(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
            folder_id=folder_id,
            existing_file_id=existing_drive_file_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Google Drive upload failed: {exc}"
        )

    if existing_doc:
        doc = crud_doc.overwrite_document(
            db,
            existing_doc,
            drive_file_id=drive_result["file_id"],
            drive_file_url=drive_result["file_url"],
            drive_folder_id=drive_result.get("folder_id") or folder_id,
            mime_type=file.content_type,
            file_size_bytes=len(file_bytes),
            uploaded_by_user_id=current_user.id,
            uploaded_by_user_name=current_user.username,
        )
    else:
        payload = CPRAppDocumentCreate(
            application_uuid=application_uuid,
            application_type=application_type,
            requirement_group=requirement_group,
            category_code=category_code,
            requirement_code=requirement_code,
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

    return CPRAppDocumentUploadResponse(
        id=doc.id,
        drive_file_id=doc.drive_file_id,
        drive_file_url=doc.drive_file_url,
        original_filename=doc.original_filename,
        requirement_group=doc.requirement_group,
        category_code=doc.category_code,
        requirement_code=doc.requirement_code,
        file_size_bytes=doc.file_size_bytes,
    )


@router.get("/{application_uuid}", response_model=CPRAppDocumentListResponse)
def list_documents(application_uuid: str, db: Session = Depends(get_db)):
    docs = crud_doc.get_documents_by_application_uuid(db, application_uuid)
    return CPRAppDocumentListResponse(data=docs, total=len(docs))


@router.delete("/{document_id}", response_model=CPRAppDocumentDeleteResponse)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    doc = crud_doc.get_document_by_id(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    delete_file_from_drive(doc.drive_file_id)
    crud_doc.soft_delete_document(db, document_id, deleted_by=current_user.username)

    return CPRAppDocumentDeleteResponse(message="Document deleted successfully.")
