# app/schemas/bulk_upload_log.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BulkUploadLogBase(BaseModel):
    batch_id:          str
    main_db_id:        Optional[int] = None
    db_entry_type:     str
    db_dtn:            str
    doc_category:      Optional[str] = None
    original_filename: str
    relative_path:     Optional[str] = None
    status:            str  # "success" | "failed"
    error_message:     Optional[str] = None
    mime_type:         Optional[str] = None
    file_size_bytes:   Optional[int] = None
    application_document_id: Optional[int] = None


class BulkUploadLogCreate(BulkUploadLogBase):
    uploaded_by_user_id:   Optional[int] = None
    uploaded_by_user_name: Optional[str] = None


class BulkUploadLogRead(BulkUploadLogBase):
    id:                    int
    uploaded_by_user_id:   Optional[int] = None
    uploaded_by_user_name: Optional[str] = None
    created_at:            Optional[datetime] = None
    # ── BAGO: enriched sa CRUD layer lang (joined mula sa linked
    # ApplicationDocument kapag successful upload) — hindi ito nakatira
    # sa BulkUploadLog table mismo.
    drive_file_url: Optional[str] = None
    drive_file_id:  Optional[str] = None

    class Config:
        from_attributes = True


class BulkUploadLogListResponse(BaseModel):
    data:     list[BulkUploadLogRead]
    total:    int
    batch_id: Optional[str] = None


class UploaderListResponse(BaseModel):
    uploaders: list[str]