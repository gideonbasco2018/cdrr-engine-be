# app/schemas/bulk_upload_history.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


# ─────────────────────────────────────────────
# Request Schemas
# ─────────────────────────────────────────────

class InsertedRecordEntry(BaseModel):
    rowNum:  int
    rsn:     str
    remarks: str = ""


class FailedRecordEntry(BaseModel):
    rowNum:  int = 0
    rsn:     str
    remarks: str = ""
    reason:  str


class UploadHistoryCreate(BaseModel):
    fileName:        str  = Field(...,    description="Name of the uploaded .xlsx file")
    uploadedBy:      str  = Field(...,    description="Username of the uploader")
    insertedCount:   int  = Field(...,    description="How many logs were successfully inserted")
    failedCount:     int  = Field(...,    description="How many rows were skipped")
    insertedRecords: List[InsertedRecordEntry] = Field(default=[], description="Successfully inserted rows")
    failedRecords:   List[FailedRecordEntry]   = Field(default=[], description="Skipped rows with reasons")


# ─────────────────────────────────────────────
# Response Schemas
# ─────────────────────────────────────────────

class InsertedRecordResponse(BaseModel):
    recordID:  int
    historyID: int
    rowNum:    int
    rsn:       str
    remarks:   Optional[str]

    class Config:
        from_attributes = True


class UploadHistoryResponse(BaseModel):
    historyID:     int
    fileName:      str
    uploadedAt:    datetime
    uploadedBy:    str
    insertedCount: int
    failedCount:   int
    failedRecords: List[Dict[str, Any]]
    records:       List[InsertedRecordResponse] = []

    class Config:
        from_attributes = True


class UploadHistoryListItem(BaseModel):
    """Lighter version for list view — no child records"""
    historyID:     int
    fileName:      str
    uploadedAt:    datetime
    uploadedBy:    str
    insertedCount: int
    failedCount:   int

    class Config:
        from_attributes = True


class PaginatedHistoryResponse(BaseModel):
    total:  int
    limit:  Optional[int]
    offset: int
    data:   List[UploadHistoryListItem]


class PaginatedRecordsResponse(BaseModel):
    total:     int
    limit:     int
    offset:    int
    historyID: int
    data:      List[InsertedRecordResponse]