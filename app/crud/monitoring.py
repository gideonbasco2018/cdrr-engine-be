from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, asc, desc, distinct
from typing import Optional
from datetime import datetime, date

from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs
from app.models.user import User
from app.models.user_groups import UserGroup

import math


# Excluded action types across both queries
EXCLUDED_ACTION_TYPES = ("REROUTE", "REASSIGNMENT")


def _exclude_action_types(query):
    """Helper: exclude REROUTE & REASSIGNMENT but keep NULL action_types."""
    return query.filter(
        or_(
            ApplicationLogs.action_type.is_(None),
            func.upper(ApplicationLogs.action_type).notin_(EXCLUDED_ACTION_TYPES),
        )
    )


# ── Tasks per User ─────────────────────────────────────────────────────────────
def get_users_task_summary(db: Session, group_id: Optional[int] = None) -> list:
    task_counts = (
        _exclude_action_types(
            db.query(
                ApplicationLogs.user_id,
                func.count().label("total"),
                func.sum(
                    case(
                        (
                            and_(
                                func.upper(ApplicationLogs.application_status) == "COMPLETED",
                                or_(
                                    ApplicationLogs.action_type.is_(None),
                                    func.upper(ApplicationLogs.action_type).notin_(EXCLUDED_ACTION_TYPES),
                                ),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("completed"),
                func.sum(
                    case(
                        (func.upper(ApplicationLogs.application_status) == "IN PROGRESS", 1),
                        else_=0,
                    )
                ).label("in_progress"),
            )
            .filter(ApplicationLogs.user_id.isnot(None))
        )
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

    if group_id:
        query = (
            query.join(UserGroup, UserGroup.user_id == User.id)
            .filter(UserGroup.group_id == group_id)
        )

    query = query.order_by(func.coalesce(task_counts.c.total, 0).desc())
    return query.all()


# ── All Records ────────────────────────────────────────────────────────────────
def get_all_records(
    db: Session,
    page: int = 1,
    page_size: int = 12,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort_col: str = "date",
    sort_dir: str = "desc",
    application_status: Optional[str] = None,
    dtn: Optional[str] = None,
    app_step: Optional[str] = None,
    # ── DTN date range ────────────────────────────────────────────────────────
    # Both are 8-digit strings produced by the frontend (YYYYMMDD).
    # The frontend pads omitted month/day with 01/01 (from) or 12/31 (to),
    # so the backend only needs to compare LEFT(DB_DTN, 8) against them.
    #
    # Example ranges:
    #   2023-only          → dtn_date_from="20230101"  dtn_date_to="20231231"
    #   2023-05 only       → dtn_date_from="20230501"  dtn_date_to="20230531"
    #   2023-05-06 only    → dtn_date_from="20230506"  dtn_date_to="20230506"
    #   2023 → 2026        → dtn_date_from="20230101"  dtn_date_to="20261231"
    dtn_date_from: Optional[str] = None,
    dtn_date_to: Optional[str] = None,
) -> dict:

    query = _exclude_action_types(
        db.query(ApplicationLogs, MainDB)
        .join(MainDB, MainDB.DB_ID == ApplicationLogs.main_db_id)
    )

    if user_id:
        query = query.filter(ApplicationLogs.user_id == user_id)

    if application_status:
        query = query.filter(
            func.upper(ApplicationLogs.application_status) == application_status.upper()
        )

    if dtn:
        query = query.filter(MainDB.DB_DTN.like(f"%{dtn}%"))

    if app_step:
        query = query.filter(
            func.upper(ApplicationLogs.application_step) == app_step.upper()
        )

    if date_from:
        query = query.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) >= date_from
        )

    if date_to:
        query = query.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) <= date_to
        )

    # ── DTN date range filter ─────────────────────────────────────────────────
    # Extract the first 8 characters of DB_DTN (which encodes YYYYMMDD) and
    # compare them as a string range.  Works because the format is zero-padded
    # and lexicographic order matches chronological order.
    #
    #   LEFT(DB_DTN, 8) >= '20230101'  AND  LEFT(DB_DTN, 8) <= '20261231'
    #
    # We validate that each prefix is exactly 8 digits before using it so that
    # a malformed value from the client is silently ignored rather than causing
    # an unexpected result.
    if dtn_date_from and len(dtn_date_from) == 8 and dtn_date_from.isdigit():
        query = query.filter(func.left(MainDB.DB_DTN, 8) >= dtn_date_from)

    if dtn_date_to and len(dtn_date_to) == 8 and dtn_date_to.isdigit():
        query = query.filter(func.left(MainDB.DB_DTN, 8) <= dtn_date_to)
    # ─────────────────────────────────────────────────────────────────────────

    sort_map = {
        "date": func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"),
        "dtn": MainDB.DB_DTN,
        "user": ApplicationLogs.user_name,
        "drug": MainDB.DB_PROD_BR_NAME,
        "timeline": ApplicationLogs.application_status,
        "step": ApplicationLogs.application_step,
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
        brand   = main.DB_PROD_BR_NAME  or ""
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
# -----------------------------
# SEAN Release queries
# -----------------------------
def get_release_records(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
    type_doc_released: Optional[str] = None,
    date_released_from: Optional[str] = None,
    date_released_to: Optional[str] = None,
    secpa_exp_from: Optional[str] = None,
    secpa_exp_to: Optional[str] = None,
    sort_by: str = "DB_DATE_EXCEL_UPLOAD",
    sort_order: str = "desc",
) -> dict:
    query = db.query(MainDB).filter(
        or_(
            MainDB.DB_SECPA_EXP_DATE.isnot(None),
            MainDB.DB_SECPA_ISSUED_ON.isnot(None),
            MainDB.DB_APP_STATUS.isnot(None),
            MainDB.DB_TYPE_DOC_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED.isnot(None),
        )
    )

    if search:
        query = query.filter(
            or_(
                MainDB.DB_APP_STATUS.ilike(f"%{search}%"),
                MainDB.DB_TYPE_DOC_RELEASED.ilike(f"%{search}%"),
                MainDB.DB_DATE_RELEASED.ilike(f"%{search}%"),
                MainDB.DB_SECPA_EXP_DATE.ilike(f"%{search}%"),
                MainDB.DB_SECPA_ISSUED_ON.ilike(f"%{search}%"),
                MainDB.DB_PROD_BR_NAME.ilike(f"%{search}%"),
                MainDB.DB_PROD_GEN_NAME.ilike(f"%{search}%"),
            )
        )

    if app_status:
        if app_status == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_APP_STATUS.is_(None), MainDB.DB_APP_STATUS == "")
            )
        else:
            query = query.filter(MainDB.DB_APP_STATUS == app_status)

    if type_doc_released:
        if type_doc_released == "__EMPTY__":
            query = query.filter(
                or_(MainDB.DB_TYPE_DOC_RELEASED.is_(None), MainDB.DB_TYPE_DOC_RELEASED == "")
            )
        else:
            query = query.filter(MainDB.DB_TYPE_DOC_RELEASED == type_doc_released)

    if date_released_from:
        query = query.filter(MainDB.DB_DATE_RELEASED >= date_released_from)
    if date_released_to:
        query = query.filter(MainDB.DB_DATE_RELEASED <= date_released_to)
    if secpa_exp_from:
        query = query.filter(MainDB.DB_SECPA_EXP_DATE >= secpa_exp_from)
    if secpa_exp_to:
        query = query.filter(MainDB.DB_SECPA_EXP_DATE <= secpa_exp_to)

    sort_column = getattr(MainDB, sort_by, MainDB.DB_DATE_EXCEL_UPLOAD)
    query = query.order_by(desc(sort_column) if sort_order == "desc" else asc(sort_column))

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": records,
    }


def get_release_app_statuses(db: Session):
    results = (
        db.query(MainDB.DB_APP_STATUS)
        .filter(MainDB.DB_APP_STATUS.isnot(None), MainDB.DB_APP_STATUS != "")
        .distinct()
        .order_by(MainDB.DB_APP_STATUS)
        .all()
    )
    return [r[0] for r in results]


def get_release_doc_types(db: Session):
    results = (
        db.query(MainDB.DB_TYPE_DOC_RELEASED)
        .filter(MainDB.DB_TYPE_DOC_RELEASED.isnot(None), MainDB.DB_TYPE_DOC_RELEASED != "")
        .distinct()
        .order_by(MainDB.DB_TYPE_DOC_RELEASED)
        .all()
    )
    return [r[0] for r in results]

# -----------------------------
# SEAN 2 Overview KPI Summary
# -----------------------------
def get_overview_summary(db: Session) -> dict:
    total = db.query(func.count(MainDB.DB_ID)).scalar() or 0

    cpr_released = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%")
    ).scalar() or 0

    on_process = db.query(func.count(MainDB.DB_ID)).filter(
        and_(
            MainDB.DB_APP_STATUS.isnot(None),
            MainDB.DB_APP_STATUS != "",
            func.upper(MainDB.DB_APP_STATUS).notin_(["COMPLETED", "DISAPPROVED", "RELEASED"])
        )
    ).scalar() or 0

    lod_released = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_TYPE_DOC_RELEASED.ilike("%LOD%")
    ).scalar() or 0

    return {
        "total_applications": total,
        "cpr_released": cpr_released,
        "on_process": on_process,
        "lod_released": lod_released,
    }


# ── CPR Trend (Received & Released) ───────────────────────────────────────────
# Valid country column mapping
_COUNTRY_COLUMN_MAP = {
    "manufacturer": MainDB.DB_PROD_MANU_COUNTRY,
    "trader": MainDB.DB_PROD_TRADER_COUNTRY,
    "repacker": MainDB.DB_PROD_REPACKER_COUNTRY,
    "importer": MainDB.DB_PROD_IMPORTER_COUNTRY,
    "distributor": MainDB.DB_PROD_DISTRI_COUNTRY,
}


def get_cpr_trend(
    db: Session,
    year: Optional[int] = None,
    country_type: Optional[str] = None,
    country: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> dict:
    """
    Returns monthly counts of received and released drug product applications.
    - Received: all records with a valid DB_DATE_RECEIVED_CENT
    - Released: records with a valid DB_DATE_RELEASED
    Filters:
      - year: restrict to a specific year (based on DB_DATE_RECEIVED_CENT for received,
              DB_DATE_RELEASED for released)
      - country_type: one of manufacturer|trader|repacker|importer|distributor
      - country: specific country value to filter on (requires country_type)
      - doc_type: filter by DB_TYPE_DOC_RELEASED value (applies to both queries)
    """

    # -- Country filter
    country_col = _COUNTRY_COLUMN_MAP.get(country_type) if country_type else None
    country_filters = []
    if country_col is not None and country:
        country_filters.append(country_col == country)

    # -- Doc type filter (optional)
    doc_type_filters = []
    if doc_type:
        doc_type_filters.append(MainDB.DB_TYPE_DOC_RELEASED == doc_type)

    # -- RECEIVED: ALL records with a valid DB_DATE_RECEIVED_CENT
    received_q = (
        db.query(
            func.date_format(
                func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"), "%Y-%m"
            ).label("period"),
            func.count(MainDB.DB_ID).label("cnt"),
        )
        .filter(
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        )
    )
    if year:
        received_q = received_q.filter(
            func.year(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) == year
        )
    for f in country_filters:
        received_q = received_q.filter(f)
    for f in doc_type_filters:
        received_q = received_q.filter(f)

    received_q = received_q.group_by("period").all()

    # -- RELEASED: records with a valid DB_DATE_RELEASED
    released_q = (
        db.query(
            func.date_format(
                func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"), "%Y-%m"
            ).label("period"),
            func.count(MainDB.DB_ID).label("cnt"),
        )
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_DATE_RELEASED != "N/A",
        )
    )
    if year:
        released_q = released_q.filter(
            func.year(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d")) == year
        )
    for f in country_filters:
        released_q = released_q.filter(f)
    for f in doc_type_filters:
        released_q = released_q.filter(f)

    released_q = released_q.group_by("period").all()

    # -- Merge into a dict by period
    trend_map = {}
    for period, cnt in received_q:
        if period:
            trend_map.setdefault(period, {"received_count": 0, "released_count": 0})
            trend_map[period]["received_count"] = int(cnt)

    for period, cnt in released_q:
        if period:
            trend_map.setdefault(period, {"received_count": 0, "released_count": 0})
            trend_map[period]["released_count"] = int(cnt)

    # Sort by period ascending
    sorted_periods = sorted(trend_map.keys())
    data = [
        {"period": p, **trend_map[p]}
        for p in sorted_periods
    ]

    # -- Get unique countries for the selected country_type
    countries = []
    if country_col is not None:
        country_rows = (
            db.query(country_col)
            .filter(
                country_col.isnot(None),
                country_col != "",
            )
            .distinct()
            .order_by(country_col)
            .all()
        )
        countries = [r[0] for r in country_rows]

    # -- Get unique doc types for the dropdown
    doc_type_rows = (
        db.query(MainDB.DB_TYPE_DOC_RELEASED)
        .filter(
            MainDB.DB_TYPE_DOC_RELEASED.isnot(None),
            MainDB.DB_TYPE_DOC_RELEASED != "",
        )
        .distinct()
        .order_by(MainDB.DB_TYPE_DOC_RELEASED)
        .all()
    )
    doc_types = [r[0] for r in doc_type_rows]

    return {"data": data, "countries": countries, "doc_types": doc_types}


def _build_processing_filters(
    query,
    year: Optional[int],
    doc_type: Optional[str],
    processing_type: Optional[str],
    entry_type: Optional[str],
    app_status: Optional[str],
    app_type: Optional[str],
    date_col,          # the SQLAlchemy column used for the year filter
):
    """Apply all optional filters to a query; return the modified query."""
    if year:
        query = query.filter(
            func.year(func.str_to_date(date_col, "%Y-%m-%d")) == year
        )
    if doc_type:
        query = query.filter(MainDB.DB_TYPE_DOC_RELEASED == doc_type)
    if processing_type:
        query = query.filter(MainDB.DB_PROCESSING_TYPE == processing_type)
    if entry_type:
        query = query.filter(MainDB.DB_ENTRY_TYPE == entry_type)
    if app_status:
        query = query.filter(MainDB.DB_APP_STATUS == app_status)
    if app_type:
        query = query.filter(MainDB.DB_APP_TYPE == app_type)
    return query
 
 
def _get_distinct_values(db: Session, column) -> list:
    rows = (
        db.query(column)
        .filter(column.isnot(None), column != "")
        .distinct()
        .order_by(column)
        .all()
    )
    return [r[0] for r in rows]
 
 
# ---------------------------------------------------------------------------
# Processing Trend  — monthly received vs released counts
# ---------------------------------------------------------------------------

def get_processing_trend(
    db: Session,
    year: Optional[int] = None,
    date_from: Optional[str] = None,   # ← NEW (YYYY-MM-DD)
    date_to: Optional[str] = None,     # ← NEW (YYYY-MM-DD)
    doc_type: Optional[str] = None,
    processing_type: Optional[str] = None,
    entry_type: Optional[str] = None,
    app_status: Optional[str] = None,
    app_type: Optional[str] = None,
    group_by: str = "month",
) -> dict:
    fmt = "%Y-%m" if group_by != "year" else "%Y"

    # ── RECEIVED ──────────────────────────────────────────────────────────
    received_q = db.query(
        func.date_format(
            func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"), fmt
        ).label("period"),
        func.count(MainDB.DB_ID).label("cnt"),
    ).filter(
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
    )
    received_q = _build_processing_filters(
        received_q, year, doc_type, processing_type,
        entry_type, app_status, app_type,
        date_col=MainDB.DB_DATE_RECEIVED_CENT,
    )
    # ← NEW: explicit date range on received
    if date_from:
        received_q = received_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            >= date_from
        )
    if date_to:
        received_q = received_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            <= date_to
        )
    received_rows = received_q.group_by("period").all()

    # ── RELEASED ──────────────────────────────────────────────────────────
    released_q = db.query(
        func.date_format(
            func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"), fmt
        ).label("period"),
        func.count(MainDB.DB_ID).label("cnt"),
    ).filter(
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
    )
    released_q = _build_processing_filters(
        released_q, year, doc_type, processing_type,
        entry_type, app_status, app_type,
        date_col=MainDB.DB_DATE_RELEASED,
    )
    # ← NEW: explicit date range on released
    if date_from:
        released_q = released_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"))
            >= date_from
        )
    if date_to:
        released_q = released_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"))
            <= date_to
        )
    released_rows = released_q.group_by("period").all()

    # ── Merge (unchanged) ─────────────────────────────────────────────────
    trend_map: dict[str, dict] = {}
    for period, cnt in received_rows:
        if period:
            trend_map.setdefault(period, {"received_count": 0, "released_count": 0})
            trend_map[period]["received_count"] = int(cnt)
    for period, cnt in released_rows:
        if period:
            trend_map.setdefault(period, {"received_count": 0, "released_count": 0})
            trend_map[period]["released_count"] = int(cnt)

    data = [
        {"period": p, **trend_map[p]}
        for p in sorted(trend_map.keys())
    ]

    return {
        "data": data,
        **_dropdown_options(db),
    }
 
 
# ---------------------------------------------------------------------------
# Processing Breakdown  — count by one categorical dimension
# ---------------------------------------------------------------------------
 
_DIMENSION_MAP = {
    "doc_type":       MainDB.DB_TYPE_DOC_RELEASED,
    "processing_type": MainDB.DB_PROCESSING_TYPE,
    "entry_type":     MainDB.DB_ENTRY_TYPE,
    "app_status":     MainDB.DB_APP_STATUS,
    "app_type":       MainDB.DB_APP_TYPE,
}
 
 
def get_processing_breakdown(
    db: Session,
    dimension: str = "doc_type",
    year: Optional[int] = None,
    doc_type: Optional[str] = None,
    processing_type: Optional[str] = None,
    entry_type: Optional[str] = None,
    app_status: Optional[str] = None,
    app_type: Optional[str] = None,
    date_from: Optional[str] = None,   # YYYY-MM-DD
    date_to: Optional[str] = None,     # YYYY-MM-DD
) -> dict:
    """
    Groups all matching MainDB records by *dimension* and returns counts.
    Useful for pie / bar breakdown charts.
    """
    col = _DIMENSION_MAP.get(dimension, MainDB.DB_TYPE_DOC_RELEASED)
 
    query = db.query(
        func.coalesce(col, "(None)").label("label"),
        func.count(MainDB.DB_ID).label("count"),
    )

    # Apply shared filters (use DB_DATE_RECEIVED_CENT for the year axis)
    query = _build_processing_filters(
        query, year, doc_type, processing_type,
        entry_type, app_status, app_type,
        date_col=MainDB.DB_DATE_RECEIVED_CENT,
    )
 
    # Optional explicit date range on DB_DATE_RECEIVED_CENT
    if date_from:
        query = query.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            >= date_from
        )
    if date_to:
        query = query.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            <= date_to
        )
 
    rows = query.group_by(col).order_by(func.count(MainDB.DB_ID).desc()).all()
 
    data = [{"label": r[0] or "—", "count": int(r[1])} for r in rows]
 
    return {
        "dimension": dimension,
        "data": data,
        **_dropdown_options(db),
    }
 
 
# ---------------------------------------------------------------------------
# Shared: populate dropdown option lists
# ---------------------------------------------------------------------------
 
def _dropdown_options(db: Session) -> dict:
    return {
        "doc_types":       _get_distinct_values(db, MainDB.DB_TYPE_DOC_RELEASED),
        "processing_types": _get_distinct_values(db, MainDB.DB_PROCESSING_TYPE),
        "entry_types":     _get_distinct_values(db, MainDB.DB_ENTRY_TYPE),
        "app_statuses":    _get_distinct_values(db, MainDB.DB_APP_STATUS),
        "app_types":       _get_distinct_values(db, MainDB.DB_APP_TYPE),
    }
 

# ---------------------------------------------------------------------------
# Summary — carry over / received / processed / pending per app type
# ---------------------------------------------------------------------------

def get_summary(
    db: Session,
    date_from: Optional[str] = None,   # YYYY-MM-DD  (start of period)
    date_to: Optional[str] = None,     # YYYY-MM-DD  (end of period)
    year: Optional[int] = None,
    doc_type: Optional[str] = None,
    processing_type: Optional[str] = None,
    entry_type: Optional[str] = None,
    app_status: Optional[str] = None,
    app_type: Optional[str] = None,
) -> dict:
    """
    Table 1 — per app_type breakdown:
      - carry_over  : received BEFORE date_from and not yet released by date_from
      - received    : received within [date_from, date_to]
      - processed   : released within [date_from, date_to]
      - total_pending: carry_over + received - processed

    Table 2 — overall DB_APP_STATUS counts (unfiltered by date, 
               but filtered by categorical params).
    """

    def _apply_cat_filters(q):
        if year:
            q = q.filter(
                func.year(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) == year
            )
        if doc_type:
            q = q.filter(MainDB.DB_TYPE_DOC_RELEASED == doc_type)
        if processing_type:
            q = q.filter(MainDB.DB_PROCESSING_TYPE == processing_type)
        if entry_type:
            q = q.filter(MainDB.DB_ENTRY_TYPE == entry_type)
        if app_status:
            q = q.filter(MainDB.DB_APP_STATUS == app_status)
        if app_type:
            q = q.filter(MainDB.DB_APP_TYPE == app_type)
        return q

    # ── Carry over: received before date_from, not yet released by date_from ──
    carry_q = db.query(
        func.coalesce(MainDB.DB_APP_TYPE, "Unknown").label("app_type"),
        func.count(MainDB.DB_ID).label("cnt"),
    ).filter(
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
    )
    if date_from:
        carry_q = carry_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            < date_from
        )
        # Not yet released by date_from
        carry_q = carry_q.filter(
            or_(
                MainDB.DB_DATE_RELEASED.is_(None),
                MainDB.DB_DATE_RELEASED == "",
                MainDB.DB_DATE_RELEASED == "N/A",
                func.date(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"))
                >= date_from,
            )
        )
    carry_q = _apply_cat_filters(carry_q)
    carry_rows = carry_q.group_by("app_type").all()

    # ── Received: within [date_from, date_to] ─────────────────────────────────
    recv_q = db.query(
        func.coalesce(MainDB.DB_APP_TYPE, "Unknown").label("app_type"),
        func.count(MainDB.DB_ID).label("cnt"),
    ).filter(
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
    )
    if date_from:
        recv_q = recv_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            >= date_from
        )
    if date_to:
        recv_q = recv_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"))
            <= date_to
        )
    recv_q = _apply_cat_filters(recv_q)
    recv_rows = recv_q.group_by("app_type").all()

    # ── Processed (released): within [date_from, date_to] ────────────────────
    proc_q = db.query(
        func.coalesce(MainDB.DB_APP_TYPE, "Unknown").label("app_type"),
        func.count(MainDB.DB_ID).label("cnt"),
    ).filter(
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
    )
    if date_from:
        proc_q = proc_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"))
            >= date_from
        )
    if date_to:
        proc_q = proc_q.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"))
            <= date_to
        )
    proc_q = _apply_cat_filters(proc_q)
    proc_rows = proc_q.group_by("app_type").all()

    # ── Merge into summary map ────────────────────────────────────────────────
    summary: dict[str, dict] = {}

    for at, cnt in carry_rows:
        summary.setdefault(at, {"carry_over": 0, "received": 0, "processed": 0})
        summary[at]["carry_over"] = int(cnt)

    for at, cnt in recv_rows:
        summary.setdefault(at, {"carry_over": 0, "received": 0, "processed": 0})
        summary[at]["received"] = int(cnt)

    for at, cnt in proc_rows:
        summary.setdefault(at, {"carry_over": 0, "received": 0, "processed": 0})
        summary[at]["processed"] = int(cnt)

    rows = [
        {
            "app_type": at,
            "carry_over": v["carry_over"],
            "received": v["received"],
            "processed": v["processed"],
            "total_pending": v["carry_over"] + v["received"] - v["processed"],
        }
        for at, v in sorted(summary.items())
    ]

    # ── Table 2 — overall DB_APP_STATUS counts ────────────────────────────────
    status_q = db.query(
        func.coalesce(MainDB.DB_APP_STATUS, "Unknown").label("status"),
        func.count(MainDB.DB_ID).label("cnt"),
    )
    status_q = _apply_cat_filters(status_q)
    status_rows = (
        status_q
        .filter(
            MainDB.DB_APP_STATUS.isnot(None),
            MainDB.DB_APP_STATUS != "",
        )
        .group_by("status")
        .order_by(func.count(MainDB.DB_ID).desc())
        .all()
    )

    overall_status = [
        {
            "label": r[0],
            "count": int(r[1]),
            "highlight": False,
            "right_align": False,
        }
        for r in status_rows
    ]

    # Build period label
    if date_from and date_to:
        period_label = f"{date_from}  →  {date_to}"
    elif date_from:
        period_label = f"From {date_from}"
    elif date_to:
        period_label = f"Until {date_to}"
    elif year:
        period_label = f"Year {year}"
    else:
        period_label = "All Records"

    return {
        "period_label": period_label,
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "overall_status": overall_status,
    }

def get_application_status_overview(
    db: Session,
    user_id: Optional[int] = None,
    group_id: Optional[int] = None,
    year: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    doc_type: Optional[str] = None,
    processing_type: Optional[str] = None,
    entry_type: Optional[str] = None,
    app_status: Optional[str] = None,
    app_type: Optional[str] = None,
) -> dict:
    query = (
        db.query(
            func.coalesce(ApplicationLogs.application_step, "Unknown").label("step"),
            func.count(ApplicationLogs.id).label("count"),
        )
        .join(MainDB, MainDB.DB_ID == ApplicationLogs.main_db_id)
        .filter(
            func.upper(ApplicationLogs.application_status) == "IN PROGRESS",
            ApplicationLogs.del_last_index == 1,
            ApplicationLogs.del_thread == "Open",
        )
    )

    if user_id:
        query = query.filter(ApplicationLogs.user_id == user_id)

    if group_id:
        query = (
            query.join(User, User.id == ApplicationLogs.user_id)
            .join(UserGroup, UserGroup.user_id == User.id)
            .filter(UserGroup.group_id == group_id)
        )

    if year:
        query = query.filter(
            func.year(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) == year
        )
    if date_from:
        query = query.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) >= date_from
        )
    if date_to:
        query = query.filter(
            func.date(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) <= date_to
        )
    if doc_type:
        query = query.filter(MainDB.DB_TYPE_DOC_RELEASED == doc_type)
    if processing_type:
        query = query.filter(MainDB.DB_PROCESSING_TYPE == processing_type)
    if entry_type:
        query = query.filter(MainDB.DB_ENTRY_TYPE == entry_type)
    if app_status:
        query = query.filter(MainDB.DB_APP_STATUS == app_status)
    if app_type:
        query = query.filter(MainDB.DB_APP_TYPE == app_type)

    rows = (
        query
        .group_by(ApplicationLogs.application_step)
        .order_by(func.count(ApplicationLogs.id).desc())
        .all()
    )

    total = sum(r[1] for r in rows)

    return {
        "total_in_progress": total,
        "data": [{"step": r[0], "count": int(r[1])} for r in rows],
    }