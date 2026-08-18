# app/schemas/bulk_upload_log.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BulkUploadLogBase(BaseModel):
    batch_id: str
    main_db_id: Optional[int] = None
    db_entry_type: str
    db_dtn: str
    doc_category: Optional[str] = None
    original_filename: str
    relative_path: Optional[str] = None
    status: str  # "success" | "failed"
    error_message: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    application_document_id: Optional[int] = None


class BulkUploadLogCreate(BulkUploadLogBase):
    uploaded_by_user_id: Optional[int] = None
    uploaded_by_user_name: Optional[str] = None


class BulkUploadLogRead(BulkUploadLogBase):
    id: int
    uploaded_by_user_id: Optional[int] = None
    uploaded_by_user_name: Optional[str] = None
    created_at: Optional[datetime] = None
    # Enriched at the CRUD layer only (joined from the linked
    # ApplicationDocument when the upload succeeded) — not a real
    # column on the BulkUploadLog table itself.
    drive_file_url: Optional[str] = None
    drive_file_id: Optional[str] = None

    class Config:
        from_attributes = True


class BulkUploadLogListResponse(BaseModel):
    data: list[BulkUploadLogRead]
    total: int  # total number of distinct BATCHES matching the filters
    total_logs: Optional[int] = (
        None  # number of log rows actually included in this response
    )
    batch_id: Optional[str] = None


class UploaderListResponse(BaseModel):
    uploaders: list[str]


class BulkUploadLogStatsResponse(BaseModel):
    total_batches: int
    total_success: int
    total_failed: int


class DateSummaryRow(BaseModel):
    date: str
    total_files: int
    total_success: int
    total_failed: int
    total_batches: int


class BulkUploadLogDateSummaryResponse(BaseModel):
    data: list[DateSummaryRow]
    total: int  # total distinct days matching the filters
