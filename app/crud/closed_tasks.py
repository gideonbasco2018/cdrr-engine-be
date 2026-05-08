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

# Philippine Standard Time helper (same pattern as your existing code)
_PHT = timezone(timedelta(hours=8))


def _now_pht() -> datetime:
    """Return current time in Philippine Standard Time (UTC+8), timezone-naive for DB."""
    return datetime.now(_PHT).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _close_active_log(db: Session, main_db_id: int, closed_at: datetime) -> Optional[ApplicationLogs]:
    """
    Mark the currently IN PROGRESS application log for this main_db_id
    as COMPLETED / permanently closed.
    Returns the updated log row (or None if no active log was found).
    """
    active_log = (
        db.query(ApplicationLogs)
        .filter(
            and_(
                ApplicationLogs.main_db_id == main_db_id,
                ApplicationLogs.application_status == "IN PROGRESS",
                ApplicationLogs.del_last_index == 1,
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
        db.flush()  # write without committing so we can grab the id below

    return active_log


# ─────────────────────────────────────────────────────────────────────
# CREATE — single
# ─────────────────────────────────────────────────────────────────────

def create(db: Session, task_in: ClosedTaskCreate) -> ClosedTask:
    """
    Permanently close ONE task:
    1. Mark the active application_log row as COMPLETED (action_type = PERMANENT_CLOSE)
    2. Insert a row in closed_tasks for audit trail
    """
    closed_at = task_in.closed_at or _now_pht()

    # Step 1 — update the active log
    active_log = _close_active_log(db, task_in.main_db_id, closed_at)
    resolved_log_id = task_in.app_log_id or (active_log.id if active_log else None)

    # Step 2 — insert closed_task record
    db_closed = ClosedTask(
        main_db_id          = task_in.main_db_id,
        app_log_id          = resolved_log_id,
        closed_by_user_id   = task_in.closed_by_user_id,
        closed_by_user_name = task_in.closed_by_user_name,
        reason_for_closing  = task_in.reason_for_closing,
        remarks             = task_in.remarks,
        closed_at           = closed_at,
    )

    db.add(db_closed)
    db.commit()
    db.refresh(db_closed)

    return db_closed


# ─────────────────────────────────────────────────────────────────────
# CREATE — bulk  (multiple tasks closed in one modal action)
# ─────────────────────────────────────────────────────────────────────

def create_bulk(db: Session, bulk_in: ClosedTaskBulkCreate) -> List[ClosedTask]:
    """
    Permanently close MULTIPLE tasks in one operation.
    All-or-nothing: rolls back on any error.
    """
    closed_at = bulk_in.closed_at or _now_pht()
    created: List[ClosedTask] = []

    try:
        for main_db_id in bulk_in.main_db_ids:
            active_log     = _close_active_log(db, main_db_id, closed_at)
            resolved_log_id = active_log.id if active_log else None

            db_closed = ClosedTask(
                main_db_id          = main_db_id,
                app_log_id          = resolved_log_id,
                closed_by_user_id   = bulk_in.closed_by_user_id,
                closed_by_user_name = bulk_in.closed_by_user_name,
                reason_for_closing  = bulk_in.reason_for_closing,
                remarks             = bulk_in.remarks,
                closed_at           = closed_at,
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
    """Check if a specific application has already been permanently closed."""
    return (
        db.query(ClosedTask)
        .filter(ClosedTask.main_db_id == main_db_id)
        .order_by(ClosedTask.closed_at.desc())
        .first()
    )


def is_already_closed(db: Session, main_db_id: int) -> bool:
    """Quick boolean check — useful as a guard before any close action."""
    return db.query(ClosedTask).filter(ClosedTask.main_db_id == main_db_id).count() > 0


def get_all(
    db    : Session,
    skip  : int = 0,
    limit : int = 100,
) -> List[ClosedTask]:
    """Return all closed tasks, newest first."""
    return (
        db.query(ClosedTask)
        .order_by(ClosedTask.closed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_by_user(
    db        : Session,
    user_name : str,
    skip      : int = 0,
    limit     : int = 100,
) -> List[ClosedTask]:
    """Return all tasks closed by a specific user."""
    return (
        db.query(ClosedTask)
        .filter(ClosedTask.closed_by_user_name == user_name)
        .order_by(ClosedTask.closed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )