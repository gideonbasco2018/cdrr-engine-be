# app/crud/bulk_upload_log.py

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case

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
        query = query.filter(
            BulkUploadLog.uploaded_by_user_name == uploaded_by_user_name
        )
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
        query.order_by(desc(BulkUploadLog.created_at)).offset(offset).limit(limit).all()
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


def get_batch_ids_paginated(
    db: Session,
    *,
    status: str | None = None,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 10,
    offset: int = 0,
) -> list[str]:
    """
    Return a list of DISTINCT batch_ids matching the given filters,
    ordered by the most recent entry within each batch (MAX(created_at)),
    then LIMIT/OFFSET applied here — this is the "page" of batches
    (not individual log rows).
    """
    query = db.query(
        BulkUploadLog.batch_id,
        func.max(BulkUploadLog.created_at).label("latest"),
    )
    query = _apply_log_filters(
        query,
        status=status,
        uploaded_by_user_name=uploaded_by_user_name,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        date_from=date_from,
        date_to=date_to,
    )
    rows = (
        query.group_by(BulkUploadLog.batch_id)
        .order_by(desc("latest"))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows]


def count_distinct_batches(
    db: Session,
    *,
    status: str | None = None,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    """Count of distinct batch_ids matching the filters — this is the
    basis for the batch-level `total_pages`."""
    subq = db.query(BulkUploadLog.batch_id)
    subq = _apply_log_filters(
        subq,
        status=status,
        uploaded_by_user_name=uploaded_by_user_name,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        date_from=date_from,
        date_to=date_to,
    )
    subq = subq.group_by(BulkUploadLog.batch_id).subquery()
    return db.query(func.count()).select_from(subq).scalar()


def get_logs_by_batch_ids(db: Session, batch_ids: list[str]) -> list[BulkUploadLog]:
    """
    Fetch ALL log rows (success + failed, no filter applied here) that
    belong to the given batch_ids. Deliberately unfiltered so a batch
    never gets cut off — we want to show every file in a batch that
    made the page, even if only some of its entries matched the
    original filter.
    """
    if not batch_ids:
        return []

    logs = (
        db.query(BulkUploadLog)
        .filter(BulkUploadLog.batch_id.in_(batch_ids))
        .order_by(desc(BulkUploadLog.created_at))
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
        log.drive_file_url = doc.drive_file_url if doc else None
        log.drive_file_id = doc.drive_file_id if doc else None

    return logs


def get_summary_stats(
    db: Session,
    *,
    db_dtn: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    """
    Global counts across ALL matching logs (not just the current page) —
    used for the top summary badges: total distinct batches, total
    successful entries, total failed entries.
    """
    base_query = db.query(BulkUploadLog)
    if db_dtn:
        base_query = base_query.filter(BulkUploadLog.db_dtn.ilike(f"%{db_dtn}%"))
    if date_from:
        base_query = base_query.filter(BulkUploadLog.created_at >= date_from)
    if date_to:
        base_query = base_query.filter(BulkUploadLog.created_at <= date_to)

    total_batches = count_distinct_batches(
        db, db_dtn=db_dtn, date_from=date_from, date_to=date_to
    )
    total_success = base_query.filter(BulkUploadLog.status == "success").count()
    total_failed = base_query.filter(BulkUploadLog.status == "failed").count()

    return {
        "total_batches": total_batches,
        "total_success": total_success,
        "total_failed": total_failed,
    }


def get_date_summary_paginated(
    db: Session,
    *,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[dict]:
    """
    One row per calendar day, most recent first — total files uploaded,
    success/failed counts, and distinct batch count for that day.
    `limit`/`offset` paginate over DAYS (naturally a small number),
    not individual log rows.
    """
    day_col = func.date(BulkUploadLog.created_at)

    query = db.query(
        day_col.label("day"),
        func.count(BulkUploadLog.id).label("total_files"),
        func.sum(case((BulkUploadLog.status == "success", 1), else_=0)).label(
            "total_success"
        ),
        func.sum(case((BulkUploadLog.status == "failed", 1), else_=0)).label(
            "total_failed"
        ),
        func.count(func.distinct(BulkUploadLog.batch_id)).label("total_batches"),
    )
    query = _apply_log_filters(
        query,
        uploaded_by_user_name=uploaded_by_user_name,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        date_from=date_from,
        date_to=date_to,
    )
    rows = (
        query.group_by(day_col)
        .order_by(desc(day_col))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "date": str(r.day),
            "total_files": r.total_files or 0,
            "total_success": r.total_success or 0,
            "total_failed": r.total_failed or 0,
            "total_batches": r.total_batches or 0,
        }
        for r in rows
    ]


def count_distinct_days(
    db: Session,
    *,
    uploaded_by_user_name: str | None = None,
    db_dtn: str | None = None,
    db_entry_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    """Count of distinct calendar days with at least one matching log."""
    day_col = func.date(BulkUploadLog.created_at)
    subq = db.query(day_col)
    subq = _apply_log_filters(
        subq,
        uploaded_by_user_name=uploaded_by_user_name,
        db_dtn=db_dtn,
        db_entry_type=db_entry_type,
        date_from=date_from,
        date_to=date_to,
    )
    subq = subq.group_by(day_col).subquery()
    return db.query(func.count()).select_from(subq).scalar()
