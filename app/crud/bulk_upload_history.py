# ============================================================
# FILE: app/crud/bulk_upload_history.py
# ============================================================

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from app.models.bulk_upload_history import BulkUploadHistory
from app.models.bulk_upload_history_records import BulkUploadHistoryRecord
PH_TZ = timezone(timedelta(hours=8)) 


def create_upload_history(
    db: Session,
    file_name:        str,
    uploaded_by:      str,
    inserted_count:   int,
    failed_count:     int,
    inserted_records: List[Dict[str, Any]],
    failed_records:   List[Dict[str, Any]],
) -> BulkUploadHistory:
    # 1. Create parent history row
    history = BulkUploadHistory(
        fileName=file_name,
        uploadedBy=uploaded_by,
        uploadedAt=datetime.now(PH_TZ),  # ← IDAGDAG ITO
        insertedCount=inserted_count,
        failedCount=failed_count,
        failedRecords=failed_records or [],
    )
    db.add(history)
    db.flush()

    # 2. Bulk insert child records
    if inserted_records:
        child_rows = [
            BulkUploadHistoryRecord(
                historyID=history.historyID,
                rowNum=r.get("rowNum", 0),
                rsn=r.get("rsn", ""),
                remarks=r.get("remarks", ""),
            )
            for r in inserted_records
        ]
        db.bulk_save_objects(child_rows)

    db.commit()
    db.refresh(history)
    return history


def get_upload_history_list(
    db: Session,
    limit:       int           = 50,
    offset:      int           = 0,
    uploaded_by: Optional[str] = None,       # ✅ String — filter by username
) -> tuple[List[BulkUploadHistory], int]:
    """
    Fetch paginated upload history, newest first.
    Child records are NOT loaded (list view shows counts only).
    """
    query = db.query(BulkUploadHistory)

    if uploaded_by is not None:
        query = query.filter(BulkUploadHistory.uploadedBy == uploaded_by)

    total   = query.count()
    records = (
        query.order_by(BulkUploadHistory.uploadedAt.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return records, total


def get_upload_history_by_id(
    db: Session,
    history_id: int,
) -> Optional[BulkUploadHistory]:
    """
    Fetch a single upload history entry.
    Child records auto-loaded via lazy='selectin' on the relationship.
    """
    return (
        db.query(BulkUploadHistory)
        .filter(BulkUploadHistory.historyID == history_id)
        .first()
    )


def get_history_records_paginated(
    db: Session,
    history_id: int,
    limit:  int           = 50,
    offset: int           = 0,
    search: Optional[str] = None,
) -> tuple[List[BulkUploadHistoryRecord], int]:
    """
    Fetch paginated inserted records for a specific history entry.
    Used by the View modal 'Inserted' tab with pagination + optional search.
    """
    query = db.query(BulkUploadHistoryRecord).filter(
        BulkUploadHistoryRecord.historyID == history_id
    )

    if search:
        query = query.filter(
            BulkUploadHistoryRecord.rsn.contains(search) |
            BulkUploadHistoryRecord.remarks.contains(search)
        )

    total   = query.count()
    records = (
        query.order_by(BulkUploadHistoryRecord.rowNum.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return records, total