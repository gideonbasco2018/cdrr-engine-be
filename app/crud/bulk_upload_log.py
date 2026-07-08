# app/crud/bulk_upload_log.py

from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.bulk_upload_log import BulkUploadLog
from app.models.application_document import ApplicationDocument
from app.schemas.bulk_upload_log import BulkUploadLogCreate


def create_log(db: Session, payload: BulkUploadLogCreate) -> BulkUploadLog:
    log = BulkUploadLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_logs_by_batch_id(db: Session, batch_id: str) -> list[BulkUploadLog]:
    return (
        db.query(BulkUploadLog)
        .filter(BulkUploadLog.batch_id == batch_id)
        .order_by(BulkUploadLog.id.asc())
        .all()
    )


def get_failed_logs_by_batch_id(db: Session, batch_id: str) -> list[BulkUploadLog]:
    return (
        db.query(BulkUploadLog)
        .filter(BulkUploadLog.batch_id == batch_id, BulkUploadLog.status == "failed")
        .order_by(BulkUploadLog.id.asc())
        .all()
    )


def get_logs_by_dtn(db: Session, db_dtn: str, limit: int = 200) -> list[BulkUploadLog]:
    return (
        db.query(BulkUploadLog)
        .filter(BulkUploadLog.db_dtn == db_dtn)
        .order_by(desc(BulkUploadLog.created_at))
        .limit(limit)
        .all()
    )


def _apply_log_filters(
    query,
    *,
    status: str | None = None,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    batch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    if status:
        query = query.filter(BulkUploadLog.status == status)
    if uploaded_by_user_name:
        query = query.filter(BulkUploadLog.uploaded_by_user_name == uploaded_by_user_name)
    if db_dtn:
        query = query.filter(BulkUploadLog.db_dtn.ilike(f"%{db_dtn}%"))
    if db_entry_type:
        query = query.filter(BulkUploadLog.db_entry_type == db_entry_type)
    if batch_id:
        query = query.filter(BulkUploadLog.batch_id == batch_id)
    if date_from:
        query = query.filter(BulkUploadLog.created_at >= date_from)
    if date_to:
        query = query.filter(BulkUploadLog.created_at <= date_to)
    return query


def get_logs(
    db: Session,
    *,
    status: str | None = None,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    batch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[BulkUploadLog]:
    """
    Pangkalahatang listahan ng logs (success + failed), may optional filters:
    status ('success'/'failed'), uploader (exact match sa username), DTN
    (partial match), entry type, batch_id, o date range (date_from/date_to,
    parehong inclusive, batay sa `created_at`). Pinaka-recent muna.

    Pag successful ang isang log at may naka-link na ApplicationDocument,
    dinadagdagan natin ito ng drive_file_url/drive_file_id (transient
    attributes lang — hindi nase-save, ginagamit lang papunta sa response).
    """
    query = db.query(BulkUploadLog)
    query = _apply_log_filters(
        query,
        status=status,
        uploaded_by_user_name=uploaded_by_user_name,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        batch_id=batch_id,
        date_from=date_from,
        date_to=date_to,
    )
    logs = (
        query.order_by(desc(BulkUploadLog.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    doc_ids = [l.application_document_id for l in logs if l.application_document_id]
    docs_by_id = {}
    if doc_ids:
        docs = (
            db.query(ApplicationDocument)
            .filter(ApplicationDocument.id.in_(doc_ids))
            .all()
        )
        docs_by_id = {d.id: d for d in docs}

    for log in logs:
        doc = docs_by_id.get(log.application_document_id)
        # Transient lang — hindi kasama sa BulkUploadLog table, pero
        # kailangan ng schema para ma-render sa response.
        log.drive_file_url = doc.drive_file_url if doc else None
        log.drive_file_id = doc.drive_file_id if doc else None

    return logs


def count_logs(
    db: Session,
    *,
    status: str | None = None,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    batch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    query = db.query(BulkUploadLog)
    query = _apply_log_filters(
        query,
        status=status,
        uploaded_by_user_name=uploaded_by_user_name,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        batch_id=batch_id,
        date_from=date_from,
        date_to=date_to,
    )
    return query.count()


def get_distinct_uploaders(db: Session) -> list[str]:
    """Para sa filter dropdown sa frontend — listahan ng lahat ng
    natatanging uploader names na may kahit isang log entry."""
    rows = (
        db.query(BulkUploadLog.uploaded_by_user_name)
        .filter(BulkUploadLog.uploaded_by_user_name.isnot(None))
        .distinct()
        .order_by(BulkUploadLog.uploaded_by_user_name.asc())
        .all()
    )
    return [r[0] for r in rows if r[0]]