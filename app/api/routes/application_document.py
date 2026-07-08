# app/api/routes/application_document.py

import io
import mimetypes
import uuid
import zipfile
from datetime import datetime

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
    find_file_in_folder,
    folder_exists,
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

def _guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"

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

    # ── Get or create the nested folder ───────────────────────────────
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
    """Upload multiple supporting documents into the same folder (db_entry_type/db_dtn/doc_category)."""

    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # ── Resolve the folder once for all files ──────────────────────────
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
            # If one file fails, the whole batch shouldn't blow up
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
                                    "Same order/length as 'files'. Each entry is the "
                                    "webkitRelativePath, e.g. 'DTN123/file.pdf' or "
                                    "'DTN123/CategoryA/file.pdf'. The first segment "
                                    "(top-level folder name) becomes the db_dtn; any "
                                    "following subfolder(s), regardless of depth, are "
                                    "joined together as the doc_category."
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
    batch_id: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload an entire folder (e.g., from an <input webkitdirectory>).
    -The top-level folder name (the first segment of the relative path) is treated as the db_dtn.
        -If multiple different top-level folders are detected in the provided 
        relative_paths (i.e., multiple DTNs in a single request), 
        they are automatically processed as separate Drive folders and database 
        records. Each file uses its own db_dtn based on its relative path.
    -Any subfolder(s) between the DTN folder and the file itself, regardless of depth, are joined 
        using / and stored as the doc_category.
    -If a file is a .zip archive, it is automatically extracted in memory. Each extracted file is 
        processed as an individual file and goes through the same file type validation, size validation, 
        folder resolution, Google Drive upload, and logging workflow. Any subfolders inside the ZIP archive 
        are appended to the doc_category, using the ZIP file's relative path as the base.
    -db_entry_type remains a required form field and is not derived from the folder structure.
    -All file upload attempts, whether successful or failed, are recorded in BulkUploadLog and grouped under a single batch_id (UUID) representing the entire upload request.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) != len(relative_paths):
        raise HTTPException(
            status_code=400,
            detail="'files' and 'relative_paths' must have the same length.",
        )

    batch_id = (batch_id or "").strip() or str(uuid.uuid4()) 
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
        """Best-effort logging — if logging itself fails, don't blow up the whole request."""
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

    async def _handle_entry(
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        rel_path: str,
        db_dtn: str,
        doc_category: str | None,
        category_parts: list[str],
    ) -> None:
        """Validate + upload ONE actual file (whether it came directly from
        the folder input, or was extracted from inside a zip) and record
        the result/log."""

        # ── Validate mime type ───────────────────────────────
        if content_type not in ALLOWED_MIME_TYPES:
            error_msg = f"File type '{content_type}' is not allowed."
            _log(
                db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                filename=filename, status="failed", error_message=error_msg,
                mime_type=content_type,
            )
            results.append(BatchUploadResult(filename=filename, success=False, error=error_msg))
            return

        # ── Size check ────────────────────────────────────────
        if len(file_bytes) > MAX_FILE_SIZE:
            error_msg = "File exceeds the 5 MB limit."
            _log(
                db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                filename=filename, status="failed", error_message=error_msg,
                mime_type=content_type, file_size_bytes=len(file_bytes),
            )
            results.append(BatchUploadResult(filename=filename, success=False, error=error_msg))
            return

        # ── Resolve (or create) the Drive folder ─────────────────
        cache_key = f"{db_entry_type}|{db_dtn}|{doc_category or ''}"
        folder_id = folder_cache.get(cache_key)
        if not folder_id:
            candidate_id = crud_doc.get_existing_folder_id(db, db_entry_type, db_dtn, doc_category)
            # Verify the cached folder is actually still alive before using
            # it — if it's already been deleted on Drive itself, don't use
            # it, just create a new one.
            if candidate_id and folder_exists(candidate_id):
                folder_id = candidate_id
            else:
                try:
                    folder_id = get_or_create_folder_path(db_entry_type, db_dtn, category_parts)
                except Exception as exc:
                    error_msg = f"Failed to prepare Drive folder: {exc}"
                    _log(db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                         filename=filename, status="failed", error_message=error_msg,
                         mime_type=content_type, file_size_bytes=len(file_bytes))
                    results.append(BatchUploadResult(filename=filename, success=False, error=error_msg))
                    return
            folder_cache[cache_key] = folder_id

        # ── Upload to Drive + persist to DB ──────────────────────
        # ── Check if there's an existing file/record with the SAME name in
        #    the same entry_type/dtn/category — if so, overwrite it instead
        #    of creating a new duplicate ────────────────────────────────
        existing_doc = crud_doc.get_existing_document_by_name(
            db, db_entry_type, db_dtn, doc_category, filename
        )
        # Also check based on the Drive folder itself (source of truth), in
        # case there's no DB record but the file already exists on Drive
        # (edge case).
        existing_drive_file_id = find_file_in_folder(filename, folder_id)

        # ── Upload (or overwrite) to Drive + persist to DB ───────────────
        try:
            drive_result = upload_file_to_drive(
                file_bytes=file_bytes,
                filename=filename,
                mime_type=content_type,
                folder_id=folder_id,
                existing_file_id=existing_drive_file_id,
            )

            if existing_doc:
                doc = crud_doc.overwrite_document(
                    db,
                    existing_doc,
                    drive_file_id=drive_result["file_id"],
                    drive_file_url=drive_result["file_url"],
                    drive_folder_id=drive_result.get("folder_id") or folder_id,
                    mime_type=content_type,
                    file_size_bytes=len(file_bytes),
                    uploaded_by_user_id=current_user.id,
                    uploaded_by_user_name=current_user.username,
                )
            else:
                payload = ApplicationDocumentCreate(
                    main_db_id=main_db_id,
                    db_entry_type=db_entry_type,
                    db_dtn=db_dtn,
                    doc_category=doc_category,
                    drive_file_id=drive_result["file_id"],
                    drive_file_url=drive_result["file_url"],
                    drive_folder_id=drive_result.get("folder_id") or folder_id,
                    original_filename=filename,
                    mime_type=content_type,
                    file_size_bytes=len(file_bytes),
                    uploaded_by_user_id=current_user.id,
                    uploaded_by_user_name=current_user.username,
                )
                doc = crud_doc.create_document(db, payload)

            _log(
                db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                filename=filename,
                status="success",
                error_message="Overwritten (replaced existing file)." if existing_doc else None,
                mime_type=content_type, file_size_bytes=len(file_bytes),
                application_document_id=doc.id,
            )

            results.append(BatchUploadResult(
                filename=filename,
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
                db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                filename=filename, status="failed", error_message=str(exc),
                mime_type=content_type, file_size_bytes=len(file_bytes),
            )
            results.append(BatchUploadResult(filename=filename, success=False, error=str(exc)))

    # ── Main loop — once per "top-level" file that arrives in the request ──
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

            file_bytes = await file.read()
            is_zip = file.filename.lower().endswith(".zip")

            # ── Not a zip: normal file, just goes through the same validate/upload ──
            if not is_zip:
                await _handle_entry(
                    file_bytes=file_bytes,
                    filename=file.filename,
                    content_type=file.content_type,
                    rel_path=rel_path,
                    db_dtn=db_dtn,
                    doc_category=doc_category,
                    category_parts=category_parts,
                )
                continue

            # ── ZIP: extract in memory, treat each entry as its own file ──
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    entries = [
                        zi for zi in zf.infolist()
                        if not zi.is_dir()
                        and not zi.filename.startswith("__MACOSX")
                        and not zi.filename.rsplit("/", 1)[-1].startswith(".")
                    ]

                    if not entries:
                        error_msg = "Zip file is empty or has no usable files."
                        _log(
                            db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                            filename=file.filename, status="failed", error_message=error_msg,
                            mime_type=file.content_type, file_size_bytes=len(file_bytes),
                        )
                        results.append(BatchUploadResult(
                            filename=file.filename, success=False, error=error_msg,
                        ))
                        continue

                    for zi in entries:
                        inner_parts = [p for p in zi.filename.split("/") if p]
                        inner_filename = inner_parts[-1]
                        inner_category_parts = category_parts + inner_parts[:-1]
                        inner_category = (
                            "/".join(inner_category_parts) if inner_category_parts else None
                        )
                        inner_bytes = zf.read(zi)
                        inner_mime = _guess_mime(inner_filename)
                        inner_rel_path = "/".join([db_dtn, *inner_category_parts, inner_filename])

                        await _handle_entry(
                            file_bytes=inner_bytes,
                            filename=inner_filename,
                            content_type=inner_mime,
                            rel_path=inner_rel_path,
                            db_dtn=db_dtn,
                            doc_category=inner_category,
                            category_parts=inner_category_parts,
                        )

            except zipfile.BadZipFile:
                error_msg = "Invalid or corrupted zip file."
                _log(
                    db_dtn=db_dtn, doc_category=doc_category, relative_path=rel_path,
                    filename=file.filename, status="failed", error_message=error_msg,
                    mime_type=file.content_type, file_size_bytes=len(file_bytes),
                )
                results.append(BatchUploadResult(
                    filename=file.filename, success=False, error=error_msg,
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
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    General view of all upload logs (success + failed),
    across all batches — with optional filters:
      - status: "success" | "failed"
      - uploaded_by: exact match on uploader's username
      - db_dtn: partial match
      - db_entry_type: exact match
      - date_from / date_to: inclusive range filter on `created_at`.
        Accepts any ISO-8601 datetime string (FastAPI/Pydantic parses it
        automatically), e.g. "2026-07-08T00:00:00.000".
    Most recent first. Used by the "Upload Logs" tab on the frontend.
    """
    logs = crud_log.get_logs(
        db,
        status=status,
        uploaded_by_user_name=uploaded_by,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    total = crud_log.count_logs(
        db,
        status=status,
        uploaded_by_user_name=uploaded_by,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        date_from=date_from,
        date_to=date_to,
    )
    return BulkUploadLogListResponse(data=logs, total=total)


@router.get("/upload-folder/logs-uploaders", response_model=UploaderListResponse)
def get_upload_log_uploaders(db: Session = Depends(get_db)):
    """List of all distinct uploader names — for the filter dropdown."""
    return UploaderListResponse(uploaders=crud_log.get_distinct_uploaders(db))


@router.get("/upload-folder/logs/{batch_id}", response_model=BulkUploadLogListResponse)
def get_upload_folder_logs(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Get all logs (success + failed) for a given batch_id."""
    logs = crud_log.get_logs_by_batch_id(db, batch_id)
    return BulkUploadLogListResponse(data=logs, total=len(logs), batch_id=batch_id)


@router.get("/upload-folder/logs/{batch_id}/failed", response_model=BulkUploadLogListResponse)
def get_upload_folder_failed_logs(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Get only the FAILED entries for a given batch_id."""
    logs = crud_log.get_failed_logs_by_batch_id(db, batch_id)
    return BulkUploadLogListResponse(data=logs, total=len(logs), batch_id=batch_id)


@router.get("/upload-folder/logs/by-dtn/{db_dtn}", response_model=BulkUploadLogListResponse)
def get_upload_folder_logs_by_dtn(
    db_dtn: str,
    db: Session = Depends(get_db),
):
    """Get recent upload logs (across all batches) for a given DTN."""
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