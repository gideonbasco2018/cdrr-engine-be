# app/api/routes/application_document.py

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import List, Annotated
from app.core.deps import get_current_active_user
from app.crud import application_document as crud_doc
from app.crud import bulk_upload_log as crud_log
from app.db.session import get_db
from app.models.user import User
from app.schemas.application_document import (
    ApplicationDocumentListResponse,
    ApplicationDocumentRead,
    DeleteDocumentResponse,
    UploadDocumentResponse,
    BatchUploadResponse,
    BatchUploadResult,
)
from app.schemas.bulk_upload_log import (
    BulkUploadLogCreate,
    BulkUploadLogListResponse,
    UploaderListResponse,
)

from app.services.google_drive import (
    delete_file_from_drive,
    get_or_create_application_folder,
    get_or_create_folder_path,
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
    main_db_id: int | None = Form(None),  
    db_entry_type: str = Form(...),
    db_dtn: str = Form(...),
    doc_category: str | None = Form(None),
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

    # ── Get or create yung nested folder ─────────────────────────────
    folder_id = crud_doc.get_existing_folder_id(db, db_entry_type, db_dtn, doc_category)
    if not folder_id:
        try:
            folder_id = get_or_create_application_folder(db_entry_type, db_dtn, doc_category)
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
        doc_category=doc_category,
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



@router.post(
    "/upload-batch",
    response_model=BatchUploadResponse,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "main_db_id": {"type": "integer", "nullable": True},
                            "db_entry_type": {"type": "string"},
                            "db_dtn": {"type": "string"},
                            "doc_category": {"type": "string", "nullable": True},
                            "files": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "binary",
                                },
                            },
                        },
                        
                        "required": ["db_entry_type", "db_dtn", "files"],
                    }
                }
            },
        }
    },
)
async def upload_documents_batch(
    db_entry_type: Annotated[str, Form(...)],
    db_dtn: Annotated[str, Form(...)],
    files: Annotated[List[UploadFile], File(...)],
    main_db_id: Annotated[int | None, Form()] = None,   
    doc_category: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload multiple supporting documents sa parehong folder (db_entry_type/db_dtn/doc_category)."""

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # ── Isang beses lang tayo mag-resolve ng folder para sa lahat ng files ──
    folder_id = crud_doc.get_existing_folder_id(db, db_entry_type, db_dtn, doc_category)
    if not folder_id:
        try:
            folder_id = get_or_create_application_folder(db_entry_type, db_dtn, doc_category)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to prepare Drive folder: {exc}",
            )

    results: list[BatchUploadResult] = []

    for file in files:
        try:
            # ── Validate mime type ───────────────────────────────
            if file.content_type not in ALLOWED_MIME_TYPES:
                results.append(BatchUploadResult(
                    filename=file.filename,
                    success=False,
                    error=f"File type '{file.content_type}' is not allowed.",
                ))
                continue

            # ── Read & size-check ────────────────────────────────
            file_bytes = await file.read()
            if len(file_bytes) > MAX_FILE_SIZE:
                results.append(BatchUploadResult(
                    filename=file.filename,
                    success=False,
                    error="File exceeds the 5 MB limit.",
                ))
                continue

            # ── Upload to Drive ──────────────────────────────────
            drive_result = upload_file_to_drive(
                file_bytes=file_bytes,
                filename=file.filename,
                mime_type=file.content_type,
                folder_id=folder_id,
            )

            # ── Persist record ───────────────────────────────────
            from app.schemas.application_document import ApplicationDocumentCreate

            payload = ApplicationDocumentCreate(
                main_db_id=main_db_id,
                db_entry_type=db_entry_type,
                db_dtn=db_dtn,
                doc_category=doc_category,
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

            results.append(BatchUploadResult(
                filename=file.filename,
                success=True,
                document=UploadDocumentResponse(
                    id=doc.id,
                    drive_file_id=doc.drive_file_id,
                    drive_file_url=doc.drive_file_url,
                    original_filename=doc.original_filename,
                    file_size_bytes=doc.file_size_bytes,
                ),
            ))

        except Exception as exc:
            # Isang file lang mag-fail, hindi dapat sumabog yung buong batch
            results.append(BatchUploadResult(
                filename=file.filename,
                success=False,
                error=str(exc),
            ))

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded

    return BatchUploadResponse(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


@router.post(
    "/upload-folder",
    response_model=BatchUploadResponse,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "main_db_id": {"type": "integer", "nullable": True},
                            "db_entry_type": {"type": "string"},
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                            },
                            "relative_paths": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Kaparehong order/length ng 'files'. Bawat entry ay "
                                    "yung webkitRelativePath, hal. 'DTN123/file.pdf' o "
                                    "'DTN123/CategoryA/file.pdf'. Yung unang segment "
                                    "(top-level folder name) ang magiging db_dtn; anumang "
                                    "sunod na subfolder (kahit ilang level pa) ay "
                                    "pinagsasama bilang doc_category."
                                ),
                            },
                        },
                        "required": ["db_entry_type", "files", "relative_paths"],
                    }
                }
            },
        }
    },
)
async def upload_documents_folder(
    db_entry_type: Annotated[str, Form(...)],
    files: Annotated[List[UploadFile], File(...)],
    relative_paths: Annotated[List[str], Form(...)],
    main_db_id: Annotated[int | None, Form()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload ng isang buong folder (hal. galing sa <input webkitdirectory>).

    - Top-level folder name (unang segment ng relative path) = db_dtn.
    - Anumang subfolder sa pagitan ng DTN folder at ng file mismo
      (anuman ang depth) ay pinagsasama-sama (joined ng '/') at siyang
      magiging doc_category.
    - db_entry_type required Form field pa rin (hindi ito ma-de-derive
      mula sa folder structure).
    - LAHAT ng file attempts (success at failed) ay nilo-log sa
      BulkUploadLog, naka-group sa isang 'batch_id' (UUID) para sa
      buong upload call na ito.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) != len(relative_paths):
        raise HTTPException(
            status_code=400,
            detail="'files' and 'relative_paths' must have the same length.",
        )

    batch_id = str(uuid.uuid4())
    results: list[BatchUploadResult] = []
    folder_cache: dict[str, str] = {}  # (entry_type|dtn|category) -> drive folder_id

    from app.schemas.application_document import ApplicationDocumentCreate

    def _log(
        *,
        db_dtn: str,
        doc_category: str | None,
        relative_path: str,
        filename: str,
        status: str,
        error_message: str | None = None,
        mime_type: str | None = None,
        file_size_bytes: int | None = None,
        application_document_id: int | None = None,
    ) -> None:
        """Best-effort logging — kung mag-fail ang pag-log, huwag isabog buong request."""
        try:
            crud_log.create_log(
                db,
                BulkUploadLogCreate(
                    batch_id=batch_id,
                    main_db_id=main_db_id,
                    db_entry_type=db_entry_type,
                    db_dtn=db_dtn,
                    doc_category=doc_category,
                    original_filename=filename,
                    relative_path=relative_path,
                    status=status,
                    error_message=error_message,
                    mime_type=mime_type,
                    file_size_bytes=file_size_bytes,
                    application_document_id=application_document_id,
                    uploaded_by_user_id=current_user.id,
                    uploaded_by_user_name=current_user.username,
                ),
            )
        except Exception as log_exc:
            print(f"[BulkUploadLog] Failed to write log for {filename}: {log_exc}")

    for file, rel_path in zip(files, relative_paths):
        db_dtn = "Unknown"
        doc_category: str | None = None
        try:
            parts = [p for p in rel_path.replace("\\", "/").split("/") if p]
            if len(parts) < 2:
                _log(
                    db_dtn="Unknown",
                    doc_category=None,
                    relative_path=rel_path,
                    filename=file.filename,
                    status="failed",
                    error_message="Invalid relative path — missing root (DTN) folder.",
                )
                results.append(BatchUploadResult(
                    filename=file.filename,
                    success=False,
                    error="Invalid relative path — missing root (DTN) folder.",
                ))
                continue

            db_dtn = parts[0].strip()
            category_parts = parts[1:-1]
            doc_category = "/".join(category_parts) if category_parts else None

            if file.content_type not in ALLOWED_MIME_TYPES:
                error_msg = f"File type '{file.content_type}' is not allowed."
                _log(
                    db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                    filename=file.filename, status="failed", error_message=error_msg,
                    mime_type=file.content_type,
                )
                results.append(BatchUploadResult(
                    filename=file.filename, success=False, error=error_msg,
                ))
                continue

            file_bytes = await file.read()
            if len(file_bytes) > MAX_FILE_SIZE:
                error_msg = "File exceeds the 5 MB limit."
                _log(
                    db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                    filename=file.filename, status="failed", error_message=error_msg,
                    mime_type=file.content_type, file_size_bytes=len(file_bytes),
                )
                results.append(BatchUploadResult(
                    filename=file.filename, success=False, error=error_msg,
                ))
                continue

            cache_key = f"{db_entry_type}|{db_dtn}|{doc_category or ''}"
            folder_id = folder_cache.get(cache_key)
            if not folder_id:
                folder_id = crud_doc.get_existing_folder_id(
                    db, db_entry_type, db_dtn, doc_category
                )
                if not folder_id:
                    try:
                        folder_id = get_or_create_folder_path(
                            db_entry_type, db_dtn, category_parts
                        )
                    except Exception as exc:
                        error_msg = f"Failed to prepare Drive folder: {exc}"
                        _log(
                            db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                            filename=file.filename, status="failed", error_message=error_msg,
                            mime_type=file.content_type, file_size_bytes=len(file_bytes),
                        )
                        results.append(BatchUploadResult(
                            filename=file.filename, success=False, error=error_msg,
                        ))
                        continue
                folder_cache[cache_key] = folder_id

            drive_result = upload_file_to_drive(
                file_bytes=file_bytes,
                filename=file.filename,
                mime_type=file.content_type,
                folder_id=folder_id,
            )

            payload = ApplicationDocumentCreate(
                main_db_id=main_db_id,
                db_entry_type=db_entry_type,
                db_dtn=db_dtn,
                doc_category=doc_category,
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

            _log(
                db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                filename=file.filename, status="success",
                mime_type=file.content_type, file_size_bytes=len(file_bytes),
                application_document_id=doc.id,
            )

            results.append(BatchUploadResult(
                filename=file.filename,
                success=True,
                document=UploadDocumentResponse(
                    id=doc.id,
                    drive_file_id=doc.drive_file_id,
                    drive_file_url=doc.drive_file_url,
                    original_filename=doc.original_filename,
                    file_size_bytes=doc.file_size_bytes,
                ),
            ))

        except Exception as exc:
            _log(
                db_dtn=db_dtn,
                doc_category=doc_category,
                relative_path=rel_path,
                filename=file.filename,
                status="failed",
                error_message=str(exc),
            )
            results.append(BatchUploadResult(
                filename=file.filename,
                success=False,
                error=str(exc),
            ))

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded

    return BatchUploadResponse(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
        batch_id=batch_id,
    )


@router.get("/upload-folder/logs", response_model=BulkUploadLogListResponse)
def get_all_upload_logs(
    status: str | None = None,
    uploaded_by: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Pangkalahatang view ng lahat ng upload logs (success + failed),
    across all batches — may optional filters:
      - status: "success" | "failed"
      - uploaded_by: exact match sa uploader's username
      - db_dtn: partial match
      - db_entry_type: exact match
    Pinaka-recent muna. Ginagamit ito ng "Upload Logs" tab sa frontend.
    """
    logs = crud_log.get_logs(
        db,
        status=status,
        uploaded_by_user_name=uploaded_by,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        limit=limit,
        offset=offset,
    )
    total = crud_log.count_logs(
        db,
        status=status,
        uploaded_by_user_name=uploaded_by,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
    )
    return BulkUploadLogListResponse(data=logs, total=total)


@router.get("/upload-folder/logs-uploaders", response_model=UploaderListResponse)
def get_upload_log_uploaders(db: Session = Depends(get_db)):
    """Listahan ng lahat ng natatanging uploader names — para sa filter dropdown."""
    return UploaderListResponse(uploaders=crud_log.get_distinct_uploaders(db))


@router.get("/upload-folder/logs/{batch_id}", response_model=BulkUploadLogListResponse)
def get_upload_folder_logs(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Kunin lahat ng logs (success + failed) para sa isang batch_id."""
    logs = crud_log.get_logs_by_batch_id(db, batch_id)
    return BulkUploadLogListResponse(data=logs, total=len(logs), batch_id=batch_id)


@router.get("/upload-folder/logs/{batch_id}/failed", response_model=BulkUploadLogListResponse)
def get_upload_folder_failed_logs(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Kunin lang yung mga FAILED entries para sa isang batch_id."""
    logs = crud_log.get_failed_logs_by_batch_id(db, batch_id)
    return BulkUploadLogListResponse(data=logs, total=len(logs), batch_id=batch_id)


@router.get("/upload-folder/logs/by-dtn/{db_dtn}", response_model=BulkUploadLogListResponse)
def get_upload_folder_logs_by_dtn(
    db_dtn: str,
    db: Session = Depends(get_db),
):
    """Kunin yung recent upload logs (lahat ng batches) para sa isang DTN."""
    logs = crud_log.get_logs_by_dtn(db, db_dtn)
    return BulkUploadLogListResponse(data=logs, total=len(logs))


@router.get("/by-dtn/{db_dtn}", response_model=ApplicationDocumentListResponse)
def list_documents_by_dtn(
    db_dtn: str,
    db: Session = Depends(get_db),
):
    """Return all non-deleted documents linked to a given DTN, across
    all entry types and document categories."""
    docs = crud_doc.get_documents_by_dtn(db, db_dtn)
    return ApplicationDocumentListResponse(data=docs, total=len(docs))