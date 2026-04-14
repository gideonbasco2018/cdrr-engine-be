# app/crud/dashboard_recent.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB


# ─── Status → badge mapping ───────────────────────────────────────────────────
def _map_status(app_status: Optional[str], del_thread: Optional[str]) -> dict:
    status_raw = (app_status or "").strip().upper()

    if status_raw == "COMPLETED":
        return {
            "status_label": "Completed",
            "status_color": "#36a420",
            "status_bg":    "#e9f7e6",
            "icon":         "✅",
        }
    elif status_raw == "IN PROGRESS" and del_thread == "Open":
        return {
            "status_label": "On Process",
            "status_color": "#f59e0b",
            "status_bg":    "#fff8e7",
            "icon":         "⏳",
        }
    else:
        return {
            "status_label": "Backlog",
            "status_color": "#e02020",
            "status_bg":    "#fde8e8",
            "icon":         "🚩",
        }


def _fmt_date(dt) -> str:
    """Formats a datetime/date → 'Mar 10'. Returns '' if None."""
    if dt is None:
        return ""
    try:
        d = dt.date() if hasattr(dt, "date") else dt
        return d.strftime("%b %-d")  # Linux — use "%b %#d" on Windows
    except Exception:
        return str(dt)[:10]


# ─── Main CRUD function ───────────────────────────────────────────────────────
def get_recent_applications(
    db: Session,
    username: str,
    limit: int = 10,
) -> list[dict]:
    """
    Returns the N most recent application_logs rows for `username`,
    joined with MainDB to pull DTN, brand name, and generic name.
    Ordered by start_date DESC.
    Only includes del_thread IN ('Open', 'Close').
    """
    rows = (
        db.query(ApplicationLogs)
        .options(joinedload(ApplicationLogs.main_db))
        .filter(
            ApplicationLogs.user_name == username,
            ApplicationLogs.del_thread.in_(["Open", "Close"]),
        )
        .order_by(desc(ApplicationLogs.start_date))
        .limit(limit)
        .all()
    )

    results = []
    for log in rows:
        main: MainDB = log.main_db

        # Exact column names from MainDB model
        dtn          = str(main.DB_DTN) if main and main.DB_DTN else ""
        brand_name   = (main.DB_PROD_BR_NAME  or "") if main else ""
        generic_name = (main.DB_PROD_GEN_NAME or "") if main else ""
        app_step     = log.application_step or ""

        results.append({
            "log_id":       log.id,
            "main_db_id":   log.main_db_id,
            "dtn":          dtn,
            "brand_name":   brand_name,
            "generic_name": generic_name,
            "app_step":     app_step,
            "date_display": _fmt_date(log.start_date),
            "start_date":   log.start_date.date() if log.start_date else None,
            **_map_status(log.application_status, log.del_thread),
        })

    return results