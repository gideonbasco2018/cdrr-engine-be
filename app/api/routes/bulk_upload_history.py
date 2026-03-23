# ============================================================
# FILE: app/api/routes/bulk_upload_history.py
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.crud.bulk_upload_history import (
    create_upload_history,
    get_upload_history_list,
    get_upload_history_by_id,
    get_history_records_paginated,
)

router = APIRouter(
    prefix="/api/bulk-upload-history",
    tags=["Doctrack - Bulk Upload History"],
    dependencies=[Depends(get_current_active_user)],
)


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class InsertedRecordEntry(BaseModel):
    rowNum:  int
    rsn:     str
    remarks: str = ""


class FailedRecordEntry(BaseModel):
    rsn:     str
    remarks: str = ""
    reason:  str


class UploadHistoryCreate(BaseModel):
    fileName:        str  = Field(...,    description="Name of the uploaded .xlsx file")
    uploadedBy:      str  = Field(...,    description="Username of the uploader")  # ✅ String
    insertedCount:   int  = Field(...,    description="How many logs were successfully inserted")
    failedCount:     int  = Field(...,    description="How many rows were skipped")
    insertedRecords: List[InsertedRecordEntry] = Field(default=[], description="Successfully inserted rows")
    failedRecords:   List[FailedRecordEntry]   = Field(default=[], description="Skipped rows with reasons")


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
    uploadedBy:    str                      # ✅ String
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
    uploadedBy:    str                      # ✅ String
    insertedCount: int
    failedCount:   int

    class Config:
        from_attributes = True


class PaginatedHistoryResponse(BaseModel):
    total:  int
    limit:  int
    offset: int
    data:   List[UploadHistoryListItem]


class PaginatedRecordsResponse(BaseModel):
    total:     int
    limit:     int
    offset:    int
    historyID: int
    data:      List[InsertedRecordResponse]


# ─────────────────────────────────────────────
# POST /api/bulk-upload-history/
# Manually save history (called from frontend if needed)
# NOTE: upload-excel endpoint already auto-saves history
# ─────────────────────────────────────────────

@router.post("/", response_model=UploadHistoryResponse, status_code=201)
def save_upload_history(
    payload: UploadHistoryCreate,
    db: Session = Depends(get_db),
):
    """
    Manually save the result of a bulk upload to history.
    Note: POST /api/doctrack/upload-excel already saves history automatically.
    This endpoint is available if you need to save history separately.

    Request body example:
    {
        "fileName":      "doctrack_march.xlsx",
        "uploadedBy":    "JLDLaciapag",
        "insertedCount": 18,
        "failedCount":   2,
        "insertedRecords": [
            { "rowNum": 1, "rsn": "20251114141418", "remarks": "Forwarded to LRD Admin" }
        ],
        "failedRecords": [
            { "rsn": "BAD001", "remarks": "", "reason": "RSN not found in DB" }
        ]
    }
    """
    record = create_upload_history(
        db=db,
        file_name=payload.fileName,
        uploaded_by=payload.uploadedBy,
        inserted_count=payload.insertedCount,
        failed_count=payload.failedCount,
        inserted_records=[r.dict() for r in payload.insertedRecords],
        failed_records=[f.dict() for f in payload.failedRecords],
    )
    return record


# ─────────────────────────────────────────────
# GET /api/bulk-upload-history/
# Paginated list (no child records — fast)
# ─────────────────────────────────────────────

@router.get("/", response_model=PaginatedHistoryResponse)
def list_upload_history(
    limit:       Optional[int] = Query(default=None),
    offset:      int           = Query(default=0,  ge=0),
    uploaded_by: Optional[str] = Query(default=None, description="Filter by username"), 
    db: Session = Depends(get_db),
):
    """
    Get paginated list of bulk upload history, newest first.
    Does NOT include child records (use GET /{id}/records for that).
    """
    records, total = get_upload_history_list(
        db=db, limit=limit, offset=offset, uploaded_by=uploaded_by
    )
    return PaginatedHistoryResponse(total=total, limit=limit, offset=offset, data=records)


# ─────────────────────────────────────────────
# GET /api/bulk-upload-history/{history_id}
# Single history entry with failed records JSON
# ─────────────────────────────────────────────

@router.get("/{history_id}", response_model=UploadHistoryResponse)
def get_history_detail(
    history_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a specific upload history entry including failed records JSON.
    Child inserted records are also loaded via relationship.
    """
    record = get_upload_history_by_id(db=db, history_id=history_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Upload history {history_id} not found")
    return record


# ─────────────────────────────────────────────
# GET /api/bulk-upload-history/{history_id}/records
# Paginated inserted records for the View modal
# ─────────────────────────────────────────────

@router.get("/{history_id}/records", response_model=PaginatedRecordsResponse)
def get_history_records(
    history_id: int,
    limit:  int           = Query(default=10, ge=1, le=200),
    offset: int           = Query(default=0,  ge=0),
    search: Optional[str] = Query(default=None, description="Search by RSN or remarks"),
    db: Session = Depends(get_db),
):
    """
    Get paginated inserted records for a specific history batch.
    Used by the View modal 'Inserted' tab with pagination + search.
    """
    records, total = get_history_records_paginated(
        db=db, history_id=history_id, limit=limit, offset=offset, search=search
    )
    return PaginatedRecordsResponse(
        total=total, limit=limit, offset=offset, historyID=history_id, data=records
    )