# app/crud/dashboard_recent.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB

import math
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
import math

def get_recent_applications(
    db: Session,
    username: str,
    limit: int = 10,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    q = (
        db.query(ApplicationLogs)
        .join(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(joinedload(ApplicationLogs.main_db))
        .filter(ApplicationLogs.user_name == username)
        .order_by(ApplicationLogs.created_at.desc())
    )

    total = q.count()
    total_pages = max(1, math.ceil(total / page_size))
    rows_orm = q.offset((page - 1) * page_size).limit(page_size).all()

    rows = []
    for log in rows_orm:
        main = log.main_db
        status = log.application_status or ""
        s = status.upper()
        if s == "COMPLETED":
            status_color, status_bg, status_label, icon = "#36a420", "#e9f7e6", "Completed", "✅"
        elif s == "IN PROGRESS":
            status_color, status_bg, status_label, icon = "#f59e0b", "#fff8e7", "In Progress", "⏳"
        else:
            status_color, status_bg, status_label, icon = "#6b7280", "#f3f4f6", status, "📄"

        rows.append({
            "log_id": log.id,
            "dtn": str(main.DB_DTN) if main and main.DB_DTN else "—",
            "brand_name": main.DB_PROD_BR_NAME if main else None,
            "generic_name": main.DB_PROD_GEN_NAME if main else None,
            "lto_company": main.DB_EST_LTO_COMP if main else None,
            "app_step": log.application_step,
            "application_status": log.application_status,
            "status_color": status_color,
            "status_bg": status_bg,
            "status_label": status_label,
            "icon": icon,
            "date_display": log.created_at.strftime("%b %d") if log.created_at else "—",
            "created_at": str(log.created_at) if log.created_at else None,
        })

    return {
        "rows": rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
    }