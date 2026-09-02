# app/schemas/cpr_app_document.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class CPRAppDocumentBase(BaseModel):
    application_uuid: str
    application_type: str
    requirement_group: str  # "technical" | "general"
    category_code: Optional[str] = None
    requirement_code: str
    drive_file_id: str
    drive_file_url: str
    drive_folder_id: Optional[str] = None
    original_filename: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None


class CPRAppDocumentCreate(CPRAppDocumentBase):
    uploaded_by_user_id: Optional[int] = None
    uploaded_by_user_name: Optional[str] = None


class CPRAppDocumentRead(CPRAppDocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_deleted: int
    created_at: Optional[datetime] = None


class CPRAppDocumentListResponse(BaseModel):
    data: list[CPRAppDocumentRead]
    total: int


class CPRAppDocumentUploadResponse(BaseModel):
    id: int
    drive_file_id: str
    drive_file_url: str
    original_filename: str
    requirement_group: str
    category_code: Optional[str] = None
    requirement_code: str
    file_size_bytes: Optional[int] = None
    message: str = "File uploaded successfully."


class CPRAppDocumentDeleteResponse(BaseModel):
    message: str
