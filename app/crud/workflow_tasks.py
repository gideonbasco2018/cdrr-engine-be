"""
CRUD: ApplicationLogs RIGHT JOIN MainDB
"""
from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import func, desc, or_, and_
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta

PHT = timezone(timedelta(hours=8))

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB


def get_logs_joined_with_main_db(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    del_thread: Optional[str] = None,
    del_last_index: Optional[int] = None,
    only_latest_per_thread: bool = False,
    application_step: Optional[str] = None,
    application_status: Optional[str] = None,
    application_decision: Optional[str] = None,
    user_name: Optional[str] = None,
    main_db_id: Optional[int] = None,
    dtn: Optional[int] = None,
    est_cat: Optional[str] = None,
    app_type: Optional[str] = None,
    db_app_status: Optional[str] = None,
    lto_company: Optional[str] = None,
    brand_name: Optional[str] = None,
    generic_name: Optional[str] = None,
    prescription: Optional[str] = None,
    processing_type: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Tuple[List[ApplicationLogs], int]:

    query = (
        db.query(ApplicationLogs)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(contains_eager(ApplicationLogs.main_db))
    )

    if only_latest_per_thread:
        latest_subq = (
            db.query(
                ApplicationLogs.main_db_id,
                ApplicationLogs.del_thread,
                func.max(ApplicationLogs.del_index).label("max_del_index"),
            )
            .filter(ApplicationLogs.del_thread.isnot(None))
            .group_by(ApplicationLogs.main_db_id, ApplicationLogs.del_thread)
            .subquery()
        )
        query = query.join(
            latest_subq,
            and_(
                ApplicationLogs.main_db_id == latest_subq.c.main_db_id,
                ApplicationLogs.del_thread == latest_subq.c.del_thread,
                ApplicationLogs.del_index == latest_subq.c.max_del_index,
            ),
        )

    if del_thread is not None:
        query = query.filter(ApplicationLogs.del_thread == del_thread)

    if del_last_index is not None:
        query = query.filter(ApplicationLogs.del_last_index == del_last_index)

    if main_db_id is not None:
        query = query.filter(ApplicationLogs.main_db_id == main_db_id)

    if application_step:
        query = query.filter(ApplicationLogs.application_step == application_step)

    if application_status:
        query = query.filter(ApplicationLogs.application_status == application_status)

    if application_decision:
        query = query.filter(ApplicationLogs.application_decision == application_decision)

    if user_name:
        query = query.filter(ApplicationLogs.user_name == user_name)

    if dtn is not None:
        query = query.filter(MainDB.DB_DTN == dtn)

    if est_cat:
        query = query.filter(MainDB.DB_EST_CAT == est_cat)

    if app_type:
        if app_type == "__EMPTY__":
            query = query.filter(or_(MainDB.DB_APP_TYPE.is_(None), MainDB.DB_APP_TYPE == ""))
        else:
            query = query.filter(MainDB.DB_APP_TYPE == app_type)

    if db_app_status:
        if db_app_status == "__EMPTY__":
            query = query.filter(or_(MainDB.DB_APP_STATUS.is_(None), MainDB.DB_APP_STATUS == ""))
        else:
            query = query.filter(MainDB.DB_APP_STATUS == db_app_status)

    if lto_company:
        query = query.filter(MainDB.DB_EST_LTO_COMP.like(f"%{lto_company}%"))

    if brand_name:
        query = query.filter(MainDB.DB_PROD_BR_NAME.like(f"%{brand_name}%"))

    if generic_name:
        query = query.filter(MainDB.DB_PROD_GEN_NAME.like(f"%{generic_name}%"))

    if prescription:
        if prescription == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_PROD_CLASS_PRESCRIP.is_(None), MainDB.DB_PROD_CLASS_PRESCRIP == "")
            )
        else:
            query = query.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)

    if processing_type:
        if processing_type == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_PROCESSING_TYPE.is_(None), MainDB.DB_PROCESSING_TYPE == "")
            )
        else:
            query = query.filter(MainDB.DB_PROCESSING_TYPE == processing_type)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                ApplicationLogs.application_step.like(pattern),
                ApplicationLogs.application_status.like(pattern),
                ApplicationLogs.user_name.like(pattern),
                ApplicationLogs.del_thread.like(pattern),
                MainDB.DB_EST_LTO_COMP.like(pattern),
                MainDB.DB_PROD_BR_NAME.like(pattern),
                MainDB.DB_PROD_GEN_NAME.like(pattern),
                MainDB.DB_REG_NO.like(pattern),
            )
        )

    total = query.count()

    LOG_SORT_FIELDS = {
        "created_at", "updated_at", "accomplished_date", "start_date",
        "del_index", "del_last_index", "application_step",
        "application_status", "user_name",
    }
    MAIN_DB_SORT_FIELDS = {
        "DB_DATE_EXCEL_UPLOAD", "DB_DTN", "DB_EST_LTO_COMP",
        "DB_PROD_BR_NAME", "DB_APP_STATUS",
    }

    if sort_by in LOG_SORT_FIELDS and hasattr(ApplicationLogs, sort_by):
        col = getattr(ApplicationLogs, sort_by)
        query = query.order_by(desc(col) if sort_order == "desc" else col)
    elif sort_by in MAIN_DB_SORT_FIELDS and hasattr(MainDB, sort_by):
        col = getattr(MainDB, sort_by)
        query = query.order_by(desc(col) if sort_order == "desc" else col)
    else:
        query = query.order_by(desc(ApplicationLogs.created_at))

    logs = query.offset(skip).limit(limit).all()
    return logs, total


def get_logs_by_thread(
    db: Session,
    del_thread: str,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[ApplicationLogs], int]:
    query = (
        db.query(ApplicationLogs)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(contains_eager(ApplicationLogs.main_db))
        .filter(ApplicationLogs.del_thread == del_thread)
        .order_by(ApplicationLogs.del_index.asc())
    )

    total = query.count()
    logs = query.offset(skip).limit(limit).all()
    return logs, total


def mark_log_as_read(
    db: Session,
    log_id: int,
) -> Optional[ApplicationLogs]:
    """
    Mark a single ApplicationLog as read.
    Sets is_read = 1 and read_at = now() only if not already read.
    """
    log = db.query(ApplicationLogs).filter(ApplicationLogs.id == log_id).first()

    if not log:
        return None

    if not log.is_read:
        log.is_read = 1
        log.read_at = datetime.now(PHT).replace(tzinfo=None)
        db.commit()
        db.refresh(log)

    return log


def mark_logs_as_received(
    db: Session,
    log_ids: List[int],
    received_by: str,
) -> Tuple[List[ApplicationLogs], int, int]:
    """
    Bulk mark ApplicationLogs as received.

    - Only updates rows where is_received = 0 (idempotent — safe to call multiple times).
    - Sets is_received = 1, received_at = now(PHT), received_by = username.
    - Returns (updated_logs, updated_count, skipped_count).
    """
    logs = (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.id.in_(log_ids))
        .all()
    )

    now_pht = datetime.now(PHT).replace(tzinfo=None)
    updated: List[ApplicationLogs] = []
    skipped: int = 0

    for log in logs:
        if log.is_received:
            # Already received — skip, no unnecessary DB write
            skipped += 1
        else:
            log.is_received = 1
            log.received_at = now_pht
            log.received_by = received_by
            updated.append(log)

    if updated:
        db.commit()
        for log in updated:
            db.refresh(log)

    return updated, len(updated), skipped