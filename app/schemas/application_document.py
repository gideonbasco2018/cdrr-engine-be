# app/schemas/application_document.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ApplicationDocumentBase(BaseModel):
    main_db_id:        int
    db_entry_type:     str
    db_dtn:            str
    doc_category:      Optional[str] = None
    drive_file_id:     str
    drive_file_url:    str
    drive_folder_id:   Optional[str] = None
    original_filename: str
    mime_type:         Optional[str] = None
    file_size_bytes:   Optional[int] = None

class ApplicationDocumentCreate(ApplicationDocumentBase):
    uploaded_by_user_id:   Optional[int] = None
    uploaded_by_user_name: Optional[str] = None


class ApplicationDocumentRead(ApplicationDocumentBase):
    id:                    int
    uploaded_by_user_id:   Optional[int]  = None
    uploaded_by_user_name: Optional[str]  = None
    is_deleted:            int
    created_at:            Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicationDocumentListResponse(BaseModel):
    data:  list[ApplicationDocumentRead]
    total: int


class UploadDocumentResponse(BaseModel):
    """Returned after a successful upload."""
    id:               int
    drive_file_id:    str
    drive_file_url:   str
    original_filename: str
    file_size_bytes:  Optional[int] = None
    message:          str = "File uploaded successfully."


class DeleteDocumentResponse(BaseModel):
    message: str

class BatchUploadResult(BaseModel):
    filename: str
    success: bool
    document: Optional[UploadDocumentResponse] = None
    error: Optional[str] = None


class BatchUploadResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchUploadResult]