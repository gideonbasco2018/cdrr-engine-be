# app/crud/dashboard.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date

from app.models.application_logs import ApplicationLogs
from app.crud.dashboard_filters import apply_counting_filters


# ─────────────────────────────────────────────────────────
# Internal: Base query scoped to a specific user
# ─────────────────────────────────────────────────────────
def _base_query(
    db: Session,
    user_id: int,
    date_from: Optional[date],
    date_to: Optional[date],
):
    """
    Shared base query filtered by:
    - user_id        -> effective user
    - del_thread     -> 'Close' OR 'Open'
    - re-route / re-assign rows excluded
    - start_date     -> optional date range
    """
    q = apply_counting_filters(db.query(ApplicationLogs), user_id)

    if date_from:
        q = q.filter(ApplicationLogs.start_date >= date_from)
    if date_to:
        q = q.filter(func.date(ApplicationLogs.start_date) <= date_to)

    return q


# ─────────────────────────────────────────────────────────
# 1. Total Received
# ─────────────────────────────────────────────────────────
def get_total_received(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """All counted log entries belonging to the user (any status)."""
    return _base_query(db, user_id, date_from, date_to).count()


# ─────────────────────────────────────────────────────────
# 2. Completed
# ─────────────────────────────────────────────────────────
def get_total_completed(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """Entries where application_status = 'COMPLETED'."""
    return (
        _base_query(db, user_id, date_from, date_to)
        .filter(ApplicationLogs.application_status == "COMPLETED")
        .count()
    )


# ─────────────────────────────────────────────────────────
# 3. On Process
# ─────────────────────────────────────────────────────────
def get_total_on_process(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """
    Entries still in-flight:
    - application_status = 'IN PROGRESS'
    - del_thread = 'Open' (currently active step)
    """
    return (
        _base_query(db, user_id, date_from, date_to)
        .filter(
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.del_thread == "Open",
        )
        .count()
    )


# ─────────────────────────────────────────────────────────
# Combined (used by /summary)
# ─────────────────────────────────────────────────────────
def get_stats_summary(
    db: Session,
    user_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Returns all 3 KPI counts."""
    return {
        "received": get_total_received(db, user_id, date_from, date_to),
        "completed": get_total_completed(db, user_id, date_from, date_to),
        "on_process": get_total_on_process(db, user_id, date_from, date_to),
    }
