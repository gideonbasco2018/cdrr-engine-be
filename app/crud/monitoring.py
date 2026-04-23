from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from typing import Optional
from datetime import datetime, date

from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs
from app.models.user import User
from app.models.user_groups import UserGroup

# ── Tasks per User ────────────────────────────────────────────────────────────
def get_users_task_summary(db: Session, group_id: Optional[int] = None) -> list:
    task_counts = (
        db.query(
            ApplicationLogs.user_id,
            func.count().label("total"),
            func.sum(
                case((func.upper(ApplicationLogs.application_status) == "COMPLETED", 1), else_=0)
            ).label("completed"),
            func.sum(
                case((func.upper(ApplicationLogs.application_status) == "IN PROGRESS", 1), else_=0)
            ).label("in_progress"),
        )
        .filter(ApplicationLogs.user_id.isnot(None))
        .group_by(ApplicationLogs.user_id)
        .subquery()
    )

    query = (
        db.query(
            User,
            func.coalesce(task_counts.c.total, 0).label("total"),
            func.coalesce(task_counts.c.completed, 0).label("completed"),
            func.coalesce(task_counts.c.in_progress, 0).label("in_progress"),
        )
        .outerjoin(task_counts, task_counts.c.user_id == User.id)
        .filter(User.is_active == True)
    )

    # ── group filter ──────────────────────────────────────────────
    if group_id:
        query = query.join(UserGroup, UserGroup.user_id == User.id)\
                     .filter(UserGroup.group_id == group_id)

    query = query.order_by(func.coalesce(task_counts.c.total, 0).desc())
    return query.all()


# ── All Records ───────────────────────────────────────────────────────────────
def get_all_records(
    db: Session,
    page: int = 1,
    page_size: int = 12,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort_col: str = "date",
    sort_dir: str = "desc",
    application_status: Optional[str] = None,  # ← NEW: e.g. "COMPLETED", "IN PROGRESS"
) -> dict:
    """
    Fetch paginated records from application_logs joined to main_db.
    Returns ALL log entries (not just latest per application).
    Optionally filter by user_id, date range, and application_status.
    """

    query = (
        db.query(ApplicationLogs, MainDB)
        .join(MainDB, MainDB.DB_ID == ApplicationLogs.main_db_id)  # ← no latest_log_sub
    )

    # Filter by user
    if user_id:
        query = query.filter(ApplicationLogs.user_id == user_id)

    # Filter by application_status
    if application_status:
        query = query.filter(
            func.upper(ApplicationLogs.application_status) == application_status.upper()
        )

    # Date filters
    if date_from:
        query = query.filter(
            func.date(
                func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")
            ) >= date_from
        )

    if date_to:
        query = query.filter(
            func.date(
                func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")
            ) <= date_to
        )

    # Sorting
    sort_map = {
        "date": func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"),
        "dtn": MainDB.DB_DTN,
        "user": ApplicationLogs.user_name,
        "drug": MainDB.DB_PROD_BR_NAME,
        "timeline": ApplicationLogs.application_status,
    }
    sort_column = sort_map.get(sort_col, sort_map["date"])
    query = query.order_by(
        sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    )

    total = query.count()
    total_pages = max(1, -(-total // page_size))
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    def _timeline(log: ApplicationLogs, main: MainDB) -> str:
        try:
            received = datetime.strptime(main.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")
            end = (
                datetime.strptime(main.DB_DATE_RELEASED, "%Y-%m-%d")
                if main.DB_DATE_RELEASED and main.DB_DATE_RELEASED != "N/A"
                else datetime.now()
            )
            diff = abs((end - received).days)
            charter = int(main.DB_TIMELINE_CITIZEN_CHARTER or 0)
            return "Within" if diff <= charter else "Beyond"
        except Exception:
            return "N/A"

    data = []
    for log, main in rows:
        brand = main.DB_PROD_BR_NAME or ""
        generic = main.DB_PROD_GEN_NAME or ""
        drug_name = (
            f"{brand} ({generic})"
            if brand and generic
            else brand or generic or "—"
        )
        data.append(
            {
                "id": main.DB_ID,
                "dtn": str(main.DB_DTN) if main.DB_DTN else None,
                "user_name": log.user_name,
                "drug_name": drug_name,
                "date_received_cent": main.DB_DATE_RECEIVED_CENT,
                "timeline": _timeline(log, main),
                "app_step": log.application_step,
                "app_status": log.application_status,
                "prescription": main.DB_PROD_CLASS_PRESCRIP,
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": data,
    }