# api/routes/fgmp_applications.py
import json
from typing import Annotated, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security_external import verify_bearer_token
from app.schemas.fgmp_applications import (
    FGMPApplicationCreate,
    FGMPApplicationResponse,
)
from app.crud import fgmp_applications as crud_application
from app.services.google_drive import upload_file_to_drive, get_or_create_folder_path

router = APIRouter(prefix="/api/fgmp-applications", tags=["FGMP Applications"])

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
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}
MAX_FILE_SIZE = 200 * 1024 * 1024


@router.post(
    "/",
    response_model=FGMPApplicationResponse,
    dependencies=[Depends(verify_bearer_token)],
)
async def create_application(
    application: Annotated[str, Form(...)],
    documents_meta: Annotated[str, Form()] = "[]",
    documents: Annotated[List[UploadFile] | None, File()] = None,
    db: Session = Depends(get_db),
):
    documents = documents or []
    # ── Parse the JSON string fields ──────────────────────────────
    try:
        payload = FGMPApplicationCreate.model_validate_json(application)
    except Exception as exc:
        raise HTTPException(422, f"Invalid 'application' JSON: {exc}")

    try:
        meta_list = json.loads(documents_meta)
    except Exception as exc:
        raise HTTPException(422, f"Invalid 'documents_meta' JSON: {exc}")

    if len(meta_list) != len(documents):
        raise HTTPException(
            422,
            "'documents_meta' length must match the number of uploaded files.",
        )

    # ── Validate + upload each file to Drive ──────────────────────
    doc_inputs = []
    for file, meta in zip(documents, meta_list):
        ext = (
            "." + file.filename.rsplit(".", 1)[-1].lower()
            if "." in file.filename
            else ""
        )
        if file.content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                415,
                f"File type '{file.content_type}' not allowed for '{file.filename}'.",
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(413, f"'{file.filename}' exceeds the 200 MB limit.")

        for required_key in ("requirement_code", "requirement_group"):
            if required_key not in meta:
                raise HTTPException(
                    422, f"Missing '{required_key}' for file '{file.filename}'."
                )

        category_parts = [
            payload.reference_number or "UNSPECIFIED",
            meta["requirement_group"],
        ]
        if meta.get("category_code"):
            category_parts.append(meta["category_code"])

        try:
            folder_id = get_or_create_folder_path(
                "eApplication",
                "FGMP",
                category_parts,
            )

            drive_result = upload_file_to_drive(
                file_bytes=file_bytes,
                filename=file.filename,
                mime_type=file.content_type,
                folder_id=folder_id,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Google Drive operation failed: {exc}",
            )
        doc_inputs.append(
            dict(
                application_type=meta.get("application_type")
                or payload.application_type
                or "FGMP",
                requirement_group=meta["requirement_group"],
                category_code=meta.get("category_code"),
                requirement_code=meta["requirement_code"],
                drive_file_id=drive_result["file_id"],
                drive_file_url=drive_result["file_url"],
                drive_folder_id=drive_result.get("folder_id") or folder_id,
                original_filename=file.filename,
                mime_type=file.content_type,
                file_size_bytes=len(file_bytes),
                uploaded_by_user_uuid=None,
                uploaded_by_user_name=None,
            )
        )

    return crud_application.create_application(db, payload, documents=doc_inputs)
