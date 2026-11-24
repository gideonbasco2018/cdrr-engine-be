# app/crud/dashboard.py

from sqlalchemy.orm import Session
from sqlalchemy import func, extract, Integer
from typing import Optional
from datetime import date

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB
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
    """COMPLETED entries na na-accomplish sa loob ng date range."""
    q = apply_counting_filters(db.query(ApplicationLogs), user_id).filter(
        ApplicationLogs.application_status == "COMPLETED"
    )
    if date_from:
        q = q.filter(func.date(ApplicationLogs.accomplished_date) >= date_from)
    if date_to:
        q = q.filter(func.date(ApplicationLogs.accomplished_date) <= date_to)
    return q.count()


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


# ─────────────────────────────────────────────────────────
# In Progress per year (all-time backlog, not date-filtered)
# ─────────────────────────────────────────────────────────
def get_in_progress_by_year(db: Session, user_id: int) -> list:
    """Open IN PROGRESS entries of the user, grouped by the year of
    MainDB.DB_DATE_RECEIVED_CENT, with a per-step breakdown inside each year."""
    year_col = extract("year", MainDB.DB_DATE_RECEIVED_CENT).cast(Integer).label("yr")
    step_col = ApplicationLogs.application_step.label("step")
    q = db.query(ApplicationLogs).join(
        MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID
    )
    rows = (
        apply_counting_filters(q, user_id)
        .filter(
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.del_thread == "Open",
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        )
        .with_entities(year_col, step_col, func.count(ApplicationLogs.id).label("n"))
        .group_by(year_col, step_col)
        .all()
    )

    by_year = {}
    for r in rows:
        entry = by_year.setdefault(r.yr, {"year": r.yr, "count": 0, "steps": {}})
        n = int(r.n)
        label = r.step or "No step"
        entry["count"] += n
        entry["steps"][label] = entry["steps"].get(label, 0) + n

    result = []
    for yr in sorted(by_year):
        entry = by_year[yr]
        steps = sorted(entry["steps"].items(), key=lambda kv: (-kv[1], kv[0]))
        result.append(
            {
                "year": entry["year"],
                "count": entry["count"],
                "steps": [{"step": s, "count": c} for s, c in steps],
            }
        )
    return result
