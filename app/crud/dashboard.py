# app/crud/dashboard.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date

from app.models.application_logs import ApplicationLogs


# ─────────────────────────────────────────────────────────
# Internal: Base query scoped to a specific user
# ─────────────────────────────────────────────────────────
def _base_query(
    db: Session,
    username: str,
    date_from: Optional[date],
    date_to: Optional[date],
):
    """
    Shared base query filtered by:
    - user_name      → effective user
    - del_thread     → 'Close' OR 'Open' (both active and finished records)
    - start_date     → optional date range
    """
    q = db.query(ApplicationLogs).filter(
        ApplicationLogs.user_name == username,
        ApplicationLogs.del_thread.in_(["Close", "Open"]),
    )

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
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """All log entries belonging to the user (any status)."""
    return _base_query(db, username, date_from, date_to).count()


# ─────────────────────────────────────────────────────────
# 2. Completed
# ─────────────────────────────────────────────────────────
def get_total_completed(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """Entries where application_status = 'COMPLETED'."""
    return (
        _base_query(db, username, date_from, date_to)
        .filter(ApplicationLogs.application_status == "COMPLETED")
        .count()
    )


# ─────────────────────────────────────────────────────────
# 3. On Process
# ─────────────────────────────────────────────────────────
def get_total_on_process(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    """
    Entries still in-flight:
    - application_status = 'IN PROGRESS'
    - del_thread = 'Open' (currently active step)
    """
    return (
        _base_query(db, username, date_from, date_to)
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
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """Returns all 3 KPI counts in one DB round-trip block."""
    received   = get_total_received(db, username, date_from, date_to)
    completed  = get_total_completed(db, username, date_from, date_to)
    on_process = get_total_on_process(db, username, date_from, date_to)

    return {
        "received":   received,
        "completed":  completed,
        "on_process": on_process,
    }