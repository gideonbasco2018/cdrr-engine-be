# app/crud/dashboard_detail.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date
import math

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB
from app.schemas.dashboard_detail import MetricDetailResponse, ApplicationLogDetail


# ─────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────

def _base_query(
    db: Session,
    username: str,
    date_from: Optional[date],
    date_to: Optional[date],
):
    """
    Base query: ApplicationLogs joined to MainDB so we can pull
    dtn / brand_name / generic_name from the parent record.
    """
    q = (
        db.query(ApplicationLogs)
        .join(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .options(joinedload(ApplicationLogs.main_db))
        .filter(
            ApplicationLogs.user_name == username,
            ApplicationLogs.del_thread.in_(["Close", "Open"]),
        )
    )
    if date_from:
        q = q.filter(ApplicationLogs.start_date >= date_from)
    if date_to:
        q = q.filter(func.date(ApplicationLogs.start_date) <= date_to)
    return q


def _apply_metric_filter(q, metric: str):
    """Narrow the base query to only rows matching the requested KPI."""
    if metric == "completed":
        q = q.filter(ApplicationLogs.application_status == "COMPLETED")
    elif metric == "on_process":
        q = q.filter(
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.del_thread == "Open",
        )
    # "received" → no additional filter
    return q


def _to_date(value):
    """Safely coerce a datetime or date value to a plain date (or None)."""
    if value is None:
        return None
    if hasattr(value, "date"):      # datetime → date
        return value.date()
    return value                    # already a date


def _row_to_detail(row: ApplicationLogs) -> ApplicationLogDetail:
    """Map ORM row (with joined main_db) → Pydantic schema."""
    main = row.main_db  # eager-loaded via joinedload

    return ApplicationLogDetail(
        log_id=row.id,
        # ── from MainDB ──────────────────────────────────────────────
        dtn=str(main.DB_DTN) if main and main.DB_DTN is not None else None,
        lto_company=main.DB_EST_LTO_COMP if main else None,
        brand_name=main.DB_PROD_BR_NAME if main else None,
        generic_name=main.DB_PROD_GEN_NAME if main else None,
        # ── from ApplicationLogs ────────────────────────────────────
        application_status=row.application_status,
        del_thread=row.del_thread,
        app_step=row.application_step,
        start_date=row.start_date,
        end_date=row.accomplished_date,
        user_name=row.user_name,
    )


# ─────────────────────────────────────────────────────────
# Public function
# ─────────────────────────────────────────────────────────

def get_metric_detail(
    db: Session,
    username: str,
    metric: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    accomplished_date_from: Optional[date] = None,  # ✅ new
    accomplished_date_to: Optional[date] = None,    # ✅ new
    app_step: Optional[str] = None,                 # ✅ new
    page: int = 1,
    page_size: int = 10,
) -> MetricDetailResponse:
    """
    Return paginated application log rows for the requested KPI metric.

    Args:
        db                      SQLAlchemy session
        username                Effective reviewer username
        metric                  One of: received | completed | on_process
        date_from               Inclusive start date filter (filters start_date)
        date_to                 Inclusive end date filter (filters start_date)
        accomplished_date_from  Filter rows where accomplished_date >= this date
        accomplished_date_to    Filter rows where accomplished_date <= this date
        app_step                Filter rows by application_step value
        page                    1-based page number
        page_size               Rows per page (1–500)
    """
    if metric not in ("received", "completed", "on_process"):
        raise ValueError(f"Unknown metric '{metric}'. Use: received | completed | on_process")

    page = max(1, page)
    page_size = max(1, min(500, page_size))

    q = _base_query(db, username, date_from, date_to)
    q = _apply_metric_filter(q, metric)

    # ── Accomplished date filter ─────────────────────────────────────────────
    if accomplished_date_from:
        q = q.filter(ApplicationLogs.accomplished_date >= accomplished_date_from)
    if accomplished_date_to:
        q = q.filter(func.date(ApplicationLogs.accomplished_date) <= accomplished_date_to)

    # ── Step filter ──────────────────────────────────────────────────────────
    if app_step:
        q = q.filter(ApplicationLogs.application_step == app_step)

    # ── Order + paginate ─────────────────────────────────────────────────────
    q = q.order_by(ApplicationLogs.start_date.desc(), ApplicationLogs.id.desc())

    total = q.count()
    total_pages = max(1, math.ceil(total / page_size))

    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    return MetricDetailResponse(
        metric=metric,
        username=username,
        date_from=date_from,
        date_to=date_to,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=[_row_to_detail(r) for r in rows],
    )