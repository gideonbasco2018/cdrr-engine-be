# app/crud/closed_tasks.py
"""
CRUD Operations for Closed Tasks
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import datetime, timezone, timedelta

from app.models.closed_tasks import ClosedTask
from app.models.application_logs import ApplicationLogs
from app.schemas.closed_tasks import ClosedTaskCreate, ClosedTaskBulkCreate

_PHT = timezone(timedelta(hours=8))


def _now_pht() -> datetime:
    return datetime.now(_PHT).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────

def _close_active_log(
    db         : Session,
    main_db_id : int,
    closed_at  : datetime,
) -> Optional[ApplicationLogs]:
    active_log = (
        db.query(ApplicationLogs)
        .filter(
            and_(
                ApplicationLogs.main_db_id         == main_db_id,
                ApplicationLogs.application_status == "IN PROGRESS",
                ApplicationLogs.del_last_index     == 1,
            )
        )
        .order_by(ApplicationLogs.del_index.desc())
        .first()
    )

    if active_log:
        active_log.application_status = "COMPLETED"
        active_log.del_last_index     = 0
        active_log.del_thread         = "Close"
        active_log.action_type        = "PERMANENT_CLOSE"
        active_log.accomplished_date  = closed_at
        db.flush()

    return active_log


def _build_closed_task(
    main_db_id   : int,
    app_log_id   : Optional[int],
    data         : ClosedTaskCreate | ClosedTaskBulkCreate,
    closed_at    : datetime,
    *,
    # bulk passes these separately since ClosedTaskBulkCreate has no app_log_id
    user_id      : int,
    user_name    : str,
) -> ClosedTask:
    """Build a ClosedTask ORM object from either a Create or BulkCreate schema."""
    return ClosedTask(
        main_db_id          = main_db_id,
        app_log_id          = app_log_id,
        closed_by_user_id   = user_id,
        closed_by_user_name = user_name,
        reason_for_closing  = data.reason_for_closing,
        remarks             = data.remarks,
        date_released       = data.date_released,
        type_doc_released   = data.type_doc_released,
        cpr_api_enabled     = data.cpr_api_enabled,
        cpr_insert_success  = data.cpr_insert_success,
        cpr_insert_error    = data.cpr_insert_error,
        cpr_skipped_by_user = data.cpr_skipped_by_user,
        closed_at           = closed_at,
    )


# ─────────────────────────────────────────────────────────────────────
# CREATE — single
# ─────────────────────────────────────────────────────────────────────

def create(db: Session, task_in: ClosedTaskCreate) -> ClosedTask:
    closed_at = task_in.closed_at or _now_pht()

    active_log      = _close_active_log(db, task_in.main_db_id, closed_at)
    resolved_log_id = task_in.app_log_id or (active_log.id if active_log else None)

    db_closed = _build_closed_task(
        main_db_id = task_in.main_db_id,
        app_log_id = resolved_log_id,
        data       = task_in,
        closed_at  = closed_at,
        user_id    = task_in.closed_by_user_id,
        user_name  = task_in.closed_by_user_name,
    )

    db.add(db_closed)
    db.commit()
    db.refresh(db_closed)
    return db_closed


# ─────────────────────────────────────────────────────────────────────
# CREATE — bulk
# ─────────────────────────────────────────────────────────────────────

def create_bulk(db: Session, bulk_in: ClosedTaskBulkCreate) -> List[ClosedTask]:
    closed_at = bulk_in.closed_at or _now_pht()
    created: List[ClosedTask] = []

    try:
        for main_db_id in bulk_in.main_db_ids:
            active_log      = _close_active_log(db, main_db_id, closed_at)
            resolved_log_id = active_log.id if active_log else None

            db_closed = _build_closed_task(
                main_db_id = main_db_id,
                app_log_id = resolved_log_id,
                data       = bulk_in,
                closed_at  = closed_at,
                user_id    = bulk_in.closed_by_user_id,
                user_name  = bulk_in.closed_by_user_name,
            )
            db.add(db_closed)
            created.append(db_closed)

        db.commit()
        for record in created:
            db.refresh(record)
        return created

    except Exception:
        db.rollback()
        raise


# ─────────────────────────────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────────────────────────────

def get_by_id(db: Session, closed_task_id: int) -> Optional[ClosedTask]:
    return db.query(ClosedTask).filter(ClosedTask.id == closed_task_id).first()


def get_by_main_db_id(db: Session, main_db_id: int) -> Optional[ClosedTask]:
    return (
        db.query(ClosedTask)
        .filter(ClosedTask.main_db_id == main_db_id)
        .order_by(ClosedTask.closed_at.desc())
        .first()
    )


def is_already_closed(db: Session, main_db_id: int) -> bool:
    return db.query(ClosedTask).filter(ClosedTask.main_db_id == main_db_id).count() > 0


def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[ClosedTask]:
    return (
        db.query(ClosedTask)
        .order_by(ClosedTask.closed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_cpr_failed(db: Session, skip: int = 0, limit: int = 100) -> List[ClosedTask]:
    """Lahat ng closed tasks na nag-fail ang CPR insert."""
    return (
        db.query(ClosedTask)
        .filter(ClosedTask.cpr_insert_success == False)  # noqa: E712
        .order_by(ClosedTask.closed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_cpr_skipped(db: Session, skip: int = 0, limit: int = 100) -> List[ClosedTask]:
    """Lahat ng closed tasks na sinadyang i-skip ang CPR insert (API OFF)."""
    return (
        db.query(ClosedTask)
        .filter(ClosedTask.cpr_skipped_by_user == True)  # noqa: E712
        .order_by(ClosedTask.closed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )