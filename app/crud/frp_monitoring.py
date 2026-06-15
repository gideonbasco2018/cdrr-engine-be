# app/crud/frp_monitoring.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import Optional
from datetime import datetime
from calendar import monthrange
from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs

FRP_TYPE = "FRP and CRP"


# Reusable base query filtered to FRP only
def _frp_query(db: Session):
    return db.query(MainDB).filter(MainDB.DB_PROCESSING_TYPE == FRP_TYPE)


def get_kpi_summary(db: Session) -> dict:
    now = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    month_end   = now.strftime(f"%Y-%m-{monthrange(now.year, now.month)[1]:02d}")

    base  = db.query(func.count(MainDB.DB_ID)).filter(MainDB.DB_PROCESSING_TYPE == FRP_TYPE)
    total = base.scalar() or 0

    cpr_released = base.filter(MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%")).scalar() or 0

    lod_released = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        MainDB.DB_TYPE_DOC_RELEASED.ilike("%LOD%"),
    ).scalar() or 0

    on_process = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        and_(
            MainDB.DB_APP_STATUS.isnot(None),
            MainDB.DB_APP_STATUS != "",
            func.upper(MainDB.DB_APP_STATUS).notin_(["COMPLETED", "DISAPPROVED", "RELEASED"]),
        ),
    ).scalar() or 0

    released_this_month = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        func.upper(MainDB.DB_APP_STATUS) == "COMPLETED",
        MainDB.DB_DATE_RELEASED >= month_start,
        MainDB.DB_DATE_RELEASED <= month_end,
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
    ).scalar() or 0

    frp_main_ids_kpi = db.query(MainDB.DB_ID).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE
    ).subquery()

    pending = db.query(func.count(ApplicationLogs.id)).filter(
        ApplicationLogs.application_step   == "Compliance",
        ApplicationLogs.application_status == "IN PROGRESS",
        ApplicationLogs.del_last_index     == "1",
        ApplicationLogs.del_thread         == "Open",
        ApplicationLogs.main_db_id.in_(frp_main_ids_kpi),
    ).scalar() or 0

    # Avg Processing Time — from DB_DATE_RECEIVED_CENT to DB_DATE_RELEASED
    avg_rows = db.query(
        MainDB.DB_DATE_RECEIVED_CENT,
        MainDB.DB_DATE_RELEASED,
    ).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
    ).all()

    avg_total_days = 0
    avg_count      = 0
    for row in avg_rows:
        try:
            start = datetime.strptime(str(row.DB_DATE_RECEIVED_CENT)[:10], "%Y-%m-%d")
            end   = datetime.strptime(str(row.DB_DATE_RELEASED)[:10],      "%Y-%m-%d")
            diff  = (end - start).days
            if diff >= 0:
                avg_total_days += diff
                avg_count      += 1
        except Exception:
            pass

    avg_tat_days = round(avg_total_days / avg_count, 1) if avg_count > 0 else None

    return {
        "total_applications":  total,
        "cpr_released":        cpr_released,
        "lod_released":        lod_released,
        "on_process":          on_process,
        "released_this_month": released_this_month,
        "pending":             pending,
        "overdue":             0,
        "avg_tat_days":        avg_tat_days,
    }


def get_status_distribution(db: Session) -> dict:
    rows = (
        db.query(MainDB.DB_APP_TYPE, func.count(MainDB.DB_ID).label("cnt"))
        .filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            MainDB.DB_APP_TYPE.isnot(None),
            MainDB.DB_APP_TYPE != "",
        )
        .group_by(MainDB.DB_APP_TYPE)
        .order_by(desc("cnt"))
        .all()
    )
    data  = [{"status": r.DB_APP_TYPE or "Unknown", "count": r.cnt} for r in rows]
    total = sum(d["count"] for d in data)
    return {"total": total, "data": data}


def get_doc_types(db: Session) -> dict:
    rows = (
        db.query(MainDB.DB_TYPE_DOC_RELEASED, func.count(MainDB.DB_ID).label("cnt"))
        .filter(MainDB.DB_PROCESSING_TYPE == FRP_TYPE)
        .group_by(MainDB.DB_TYPE_DOC_RELEASED)
        .order_by(desc("cnt"))
        .all()
    )
    data = [
        {
            "doc_type": r[0] if r[0] and r[0].strip() else "Not Yet Assigned",
            "count":    r[1],
        }
        for r in rows
    ]
    # Merge all null/empty rows into a single "Not Yet Assigned" entry
    merged = {}
    for d in data:
        key = d["doc_type"]
        merged[key] = merged.get(key, 0) + d["count"]
    data = [{"doc_type": k, "count": v} for k, v in merged.items()]
    data.sort(key=lambda x: x["count"], reverse=True)
    total = sum(d["count"] for d in data)
    return {"total": total, "data": data}


COUNTRY_COL_MAP = {
    "manufacturer": MainDB.DB_PROD_MANU_COUNTRY,
    "trader":       MainDB.DB_PROD_TRADER_COUNTRY,
    "importer":     MainDB.DB_PROD_IMPORTER_COUNTRY,
    "distributor":  MainDB.DB_PROD_DISTRI_COUNTRY,
    "repacker":     MainDB.DB_PROD_REPACKER_COUNTRY,
}


def get_top_countries(db: Session, entity_type: str = "manufacturer") -> dict:
    col  = COUNTRY_COL_MAP.get(entity_type, MainDB.DB_PROD_MANU_COUNTRY)
    rows = (
        db.query(col.label("country"), func.count(MainDB.DB_ID).label("total"))
        .filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            col.isnot(None),
            col != "",
        )
        .group_by(col)
        .order_by(desc("total"))
        .all()
    )
    data = []
    for r in rows:
        approved = db.query(func.count(MainDB.DB_ID)).filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            col == r.country,
            MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%"),
        ).scalar() or 0
        rejected = db.query(func.count(MainDB.DB_ID)).filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            col == r.country,
            MainDB.DB_TYPE_DOC_RELEASED.ilike("%LOD%"),
        ).scalar() or 0
        data.append({
            "country":  r.country,
            "total":    r.total,
            "approved": approved,
            "rejected": rejected,
            "pending":  r.total - approved - rejected,
        })
    return {"entity_type": entity_type, "data": data}


def get_product_categories(db: Session) -> dict:
    # Try each column in priority order until one has data
    for col in [
        MainDB.DB_PHARMA_PROD_CAT_LABEL,
        MainDB.DB_PROD_CLASS_PRESCRIP,
        MainDB.DB_PROD_CAT,
        MainDB.DB_APP_TYPE,
    ]:
        rows = (
            db.query(col.label("category"), func.count(MainDB.DB_ID).label("cnt"))
            .filter(
                MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
                col.isnot(None),
                col != "",
            )
            .group_by(col)
            .order_by(desc("cnt"))
            .all()
        )
        if rows:
            data  = [{"category": r.category, "count": r.cnt} for r in rows]
            total = sum(d["count"] for d in data)
            return {"total": total, "data": data}
    return {"total": 0, "data": []}


def get_compliance(db: Session) -> dict:
    now = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    month_end   = now.strftime(f"%Y-%m-{monthrange(now.year, now.month)[1]:02d}")

    # Subquery — FRP and CRP main_db IDs only
    frp_main_ids = db.query(MainDB.DB_ID).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE
    ).subquery()

    # ── Pending Requests ──────────────────────────────────────────────────────
    pending_requests = db.query(func.count(ApplicationLogs.id)).filter(
        ApplicationLogs.application_step   == "Compliance",
        ApplicationLogs.application_status == "IN PROGRESS",
        ApplicationLogs.del_last_index     == "1",
        ApplicationLogs.del_thread         == "Open",
        ApplicationLogs.main_db_id.in_(frp_main_ids),
    ).scalar() or 0

    # ── Avg Days Awaiting ─────────────────────────────────────────────────────
    compliance_rows = db.query(
        ApplicationLogs.start_date,
        ApplicationLogs.accomplished_date,
    ).filter(
        ApplicationLogs.application_step   == "Compliance",
        ApplicationLogs.application_status == "Completed",
        ApplicationLogs.del_last_index     == "1",
        ApplicationLogs.start_date.isnot(None),
        ApplicationLogs.accomplished_date.isnot(None),
        ApplicationLogs.main_db_id.in_(frp_main_ids),
    ).all()

    total_days = 0
    days_count = 0
    for row in compliance_rows:
        try:
            start = row.start_date if isinstance(row.start_date, datetime) \
                else datetime.strptime(str(row.start_date)[:19], "%Y-%m-%d %H:%M:%S")
            end   = row.accomplished_date if isinstance(row.accomplished_date, datetime) \
                else datetime.strptime(str(row.accomplished_date)[:19], "%Y-%m-%d %H:%M:%S")
            diff  = (end - start).days
            if diff >= 0:
                total_days += diff
                days_count += 1
        except Exception:
            pass

    avg_days_awaiting = round(total_days / days_count, 1) if days_count > 0 else None

    # ── Issued This Month ─────────────────────────────────────────────────────
    issued_this_month = db.query(func.count(ApplicationLogs.id)).filter(
        ApplicationLogs.application_step   == "Compliance",
        ApplicationLogs.application_status == "Completed",
        ApplicationLogs.del_last_index     == "1",
        ApplicationLogs.accomplished_date.isnot(None),
        func.date_format(ApplicationLogs.accomplished_date, "%Y-%m-%d") >= month_start,
        func.date_format(ApplicationLogs.accomplished_date, "%Y-%m-%d") <= month_end,
        ApplicationLogs.main_db_id.in_(frp_main_ids),
    ).scalar() or 0

    # ── Resolved ──────────────────────────────────────────────────────────────
    resolved = db.query(func.count(ApplicationLogs.id)).filter(
        ApplicationLogs.application_step   == "Compliance",
        ApplicationLogs.application_status == "Completed",
        ApplicationLogs.del_last_index     == "1",
        ApplicationLogs.main_db_id.in_(frp_main_ids),
    ).scalar() or 0

    return {
        "pending_requests":  pending_requests,
        "avg_days_awaiting": avg_days_awaiting,
        "issued_this_month": issued_this_month,
        "resolved":          resolved,
    }


def get_cpr_trend(db: Session, year: Optional[int] = None) -> dict:
    received_q = (
        db.query(
            func.date_format(
                func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"), "%Y-%m"
            ).label("period"),
            func.count(MainDB.DB_ID).label("cnt"),
        )
        .filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        )
    )
    if year:
        received_q = received_q.filter(
            func.year(func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d")) == year
        )
    received_q = received_q.group_by("period").all()

    released_q = (
        db.query(
            func.date_format(
                func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"), "%Y-%m"
            ).label("period"),
            func.count(MainDB.DB_ID).label("cnt"),
        )
        .filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_DATE_RELEASED != "N/A",
        )
    )
    if year:
        released_q = released_q.filter(
            func.year(func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d")) == year
        )
    released_q = released_q.group_by("period").all()

    trend_map = {}
    for period, cnt in received_q:
        if period:
            trend_map.setdefault(period, {"received_count": 0, "released_count": 0})
            trend_map[period]["received_count"] = int(cnt)
    for period, cnt in released_q:
        if period:
            trend_map.setdefault(period, {"received_count": 0, "released_count": 0})
            trend_map[period]["released_count"] = int(cnt)

    if not trend_map:
        return {"data": []}

    # ── Fill every month between first and last so nothing is skipped ─────────
    sorted_periods = sorted(trend_map.keys())
    first = datetime.strptime(sorted_periods[0],  "%Y-%m")
    last  = datetime.strptime(sorted_periods[-1], "%Y-%m")

    filled = []
    cursor = first
    while cursor <= last:
        key = cursor.strftime("%Y-%m")
        entry = trend_map.get(key, {"received_count": 0, "released_count": 0})
        filled.append({"period": key, **entry})
        # advance to next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    return {"data": filled}


def get_recent_activity(db: Session, limit: int = 10) -> dict:
    rows = (
        db.query(MainDB)
        .filter(MainDB.DB_PROCESSING_TYPE == FRP_TYPE)
        .order_by(desc(MainDB.DB_DATE_EXCEL_UPLOAD))
        .limit(limit)
        .all()
    )
    data = [
        {
            "app_no":       str(r.DB_DTN) if r.DB_DTN else None,
            "product_name": r.DB_PROD_BR_NAME or r.DB_PROD_GEN_NAME,
            "app_status":   r.DB_APP_STATUS,
            "doc_type":     r.DB_TYPE_DOC_RELEASED,
            "release_date": r.DB_DATE_RELEASED,
            "company":      r.DB_EST_LTO_COMP,
        }
        for r in rows
    ]
    return {"data": data}


def get_alerts(db: Session) -> dict:
    now = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    month_end   = now.strftime(f"%Y-%m-{monthrange(now.year, now.month)[1]:02d}")

    alerts = []

    no_status = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        or_(MainDB.DB_APP_STATUS.is_(None), MainDB.DB_APP_STATUS == ""),
    ).scalar() or 0

    on_process = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        and_(
            MainDB.DB_APP_STATUS.isnot(None),
            MainDB.DB_APP_STATUS != "",
            func.upper(MainDB.DB_APP_STATUS).notin_(["COMPLETED", "DISAPPROVED", "RELEASED"]),
        ),
    ).scalar() or 0

    released_this_month = db.query(func.count(MainDB.DB_ID)).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
        MainDB.DB_DATE_RELEASED >= month_start,
        MainDB.DB_DATE_RELEASED <= month_end,
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
    ).scalar() or 0

    if no_status > 0:
        alerts.append({
            "level":   "critical",
            "message": f"{no_status} FRP record{'s' if no_status != 1 else ''} with no application status — review required",
        })
    if on_process > 0:
        alerts.append({
            "level":   "warning",
            "message": f"{on_process} FRP application{'s' if on_process != 1 else ''} currently on process",
        })
    if released_this_month > 0:
        alerts.append({
            "level":   "info",
            "message": f"{released_this_month} FRP application{'s' if released_this_month != 1 else ''} released this month",
        })

    return {"data": alerts}


def get_app_status_breakdown(db: Session) -> dict:
    rows = (
        db.query(MainDB.DB_APP_STATUS, func.count(MainDB.DB_ID).label("cnt"))
        .filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            MainDB.DB_APP_STATUS.isnot(None),
            MainDB.DB_APP_STATUS != "",
        )
        .group_by(MainDB.DB_APP_STATUS)
        .order_by(desc("cnt"))
        .all()
    )
    data  = [{"status": r[0] or "Unknown", "count": r[1]} for r in rows]
    total = sum(d["count"] for d in data)
    return {"total": total, "data": data}


def get_reviewer_workload(db: Session) -> dict:
    from app.models.application_logs import ApplicationLogs
    from app.models.user import User

    frp_main_ids = db.query(MainDB.DB_ID).filter(
        MainDB.DB_PROCESSING_TYPE == FRP_TYPE
    ).subquery()

    total_rows = (
        db.query(ApplicationLogs.user_name, func.count(ApplicationLogs.id).label("total"))
        .filter(
            ApplicationLogs.main_db_id.in_(frp_main_ids),
            ApplicationLogs.user_name.isnot(None),
            ApplicationLogs.user_name != "",
            ApplicationLogs.del_last_index == "1",
        )
        .group_by(ApplicationLogs.user_name)
        .all()
    )

    completed_rows = (
        db.query(ApplicationLogs.user_name, func.count(ApplicationLogs.id).label("completed"))
        .filter(
            ApplicationLogs.main_db_id.in_(frp_main_ids),
            ApplicationLogs.user_name.isnot(None),
            ApplicationLogs.user_name != "",
            ApplicationLogs.del_last_index     == "1",
            ApplicationLogs.application_status == "Completed",
        )
        .group_by(ApplicationLogs.user_name)
        .all()
    )

    total_map     = {r.user_name: r.total     for r in total_rows}
    completed_map = {r.user_name: r.completed for r in completed_rows}

    data = []
    for user_name, total in total_map.items():
        completed = completed_map.get(user_name, 0)
        data.append({
            "name":      user_name,
            "total":     total,
            "completed": completed,
            "pending":   total - completed,
        })
    data.sort(key=lambda x: x["total"], reverse=True)
    return {"data": data}


# ── Field Suggestions — live autocomplete for text inputs ────────────────────
SUGGESTION_COL_MAP = {
    "lto_company":  MainDB.DB_EST_LTO_COMP,
    "brand_name":   MainDB.DB_PROD_BR_NAME,
    "generic_name": MainDB.DB_PROD_GEN_NAME,
    "dosage_form":  MainDB.DB_PROD_DOS_FORM,
    "uploaded_by":  MainDB.DB_USER_UPLOADER,
    "manufacturer": MainDB.DB_PROD_MANU,
    "trader":       MainDB.DB_PROD_TRADER,
    "importer":     MainDB.DB_PROD_IMPORTER,
    "distributor":  MainDB.DB_PROD_DISTRI,
    "repacker":     MainDB.DB_PROD_REPACKER,
}

def get_field_suggestions(db: Session, field: str, q: str, limit: int = 10) -> list:
    col = SUGGESTION_COL_MAP.get(field)
    if col is None or not q or len(q.strip()) < 2:
        return []
    rows = (
        db.query(col)
        .filter(
            MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
            col.isnot(None),
            col != "",
            col.ilike(f"%{q.strip()}%"),
        )
        .distinct()
        .order_by(col)
        .limit(limit)
        .all()
    )
    return [r[0] for r in rows if r[0] and str(r[0]).strip()]


# ── Filter Options — populate advanced filter dropdowns ───────────────────────
def get_filter_options(db: Session) -> dict:
    def distinct_col(col, limit: int = 200):
        rows = (
            db.query(col)
            .filter(
                MainDB.DB_PROCESSING_TYPE == FRP_TYPE,
                col.isnot(None),
                col != "",
            )
            .distinct()
            .order_by(col)
            .limit(limit)
            .all()
        )
        return [r[0] for r in rows if r[0] and str(r[0]).strip()]

    return {
        "est_cats":               distinct_col(MainDB.DB_EST_CAT),
        "doc_types":              distinct_col(MainDB.DB_TYPE_DOC_RELEASED),
        "app_types":              distinct_col(MainDB.DB_APP_TYPE),
        "manufacturer_countries": distinct_col(MainDB.DB_PROD_MANU_COUNTRY),
        "trader_countries":       distinct_col(MainDB.DB_PROD_TRADER_COUNTRY),
        "importer_countries":     distinct_col(MainDB.DB_PROD_IMPORTER_COUNTRY),
        "distributor_countries":  distinct_col(MainDB.DB_PROD_DISTRI_COUNTRY),
        "repacker_countries":     distinct_col(MainDB.DB_PROD_REPACKER_COUNTRY),
    }


# ── Applications List — supports all advanced filter params ───────────────────
def get_applications_list(
    db: Session,
    # quick-filter preset
    filter_type: Optional[str] = None,
    # DTN multi-search
    search: Optional[str] = None,
    # period filter (YYYY-MM)
    period: Optional[str] = None,
    # period_type: "received" | "released" | "both" (default)
    period_type: Optional[str] = None,
    # pagination
    page: int = 1,
    page_size: int = 100,
    # ── general advanced ──────────────────────────────────────────────────
    est_cat: Optional[str] = None,
    app_type: Optional[str] = None,
    lto_company: Optional[str] = None,
    brand_name: Optional[str] = None,
    generic_name: Optional[str] = None,
    dosage_form: Optional[str] = None,
    doc_type: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    upload_date_from: Optional[str] = None,
    upload_date_to: Optional[str] = None,
    date_received_from: Optional[str] = None,
    date_received_to: Optional[str] = None,
    date_released_from: Optional[str] = None,
    date_released_to: Optional[str] = None,
    # ── supply chain advanced ─────────────────────────────────────────────
    manufacturer: Optional[str] = None,
    manufacturer_country: Optional[str] = None,
    trader: Optional[str] = None,
    trader_country: Optional[str] = None,
    importer: Optional[str] = None,
    importer_country: Optional[str] = None,
    distributor: Optional[str] = None,
    distributor_country: Optional[str] = None,
    repacker: Optional[str] = None,
    repacker_country: Optional[str] = None,
) -> dict:
    now = datetime.now()
    month_start = now.strftime("%Y-%m-01")
    month_end   = now.strftime(f"%Y-%m-{monthrange(now.year, now.month)[1]:02d}")

    query = db.query(MainDB).filter(MainDB.DB_PROCESSING_TYPE == FRP_TYPE)

    # ── Quick-filter presets ──────────────────────────────────────────────────
    if filter_type == "released_this_month":
        query = query.filter(
            func.upper(MainDB.DB_APP_STATUS) == "COMPLETED",
            MainDB.DB_DATE_RELEASED >= month_start,
            MainDB.DB_DATE_RELEASED <= month_end,
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_DATE_RELEASED != "N/A",
        )
    elif filter_type == "pending_compliance":
        pending_ids_subq = db.query(ApplicationLogs.main_db_id).filter(
            ApplicationLogs.application_step   == "Compliance",
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.del_last_index     == "1",
            ApplicationLogs.del_thread         == "Open",
        ).subquery()
        query = query.filter(MainDB.DB_ID.in_(pending_ids_subq))
    elif filter_type == "overdue":
        query = query.filter(MainDB.DB_ID == -1)  # placeholder

    # ── Period filter ─────────────────────────────────────────────────────────
    if period:
        if period_type == "received":
            query = query.filter(
                func.date_format(
                    func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"), "%Y-%m"
                ) == period
            )
        elif period_type == "released":
            query = query.filter(
                func.date_format(
                    func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"), "%Y-%m"
                ) == period
            )
        else:
            # default "both" — original OR behaviour
            query = query.filter(
                or_(
                    func.date_format(
                        func.str_to_date(MainDB.DB_DATE_RECEIVED_CENT, "%Y-%m-%d"), "%Y-%m"
                    ) == period,
                    func.date_format(
                        func.str_to_date(MainDB.DB_DATE_RELEASED, "%Y-%m-%d"), "%Y-%m"
                    ) == period,
                )
            )

    # ── DTN multi-search ──────────────────────────────────────────────────────
    if search:
        search_terms = [s.strip() for s in search.replace(",", "\n").split("\n") if s.strip()]
        if search_terms:
            query = query.filter(
                or_(*[MainDB.DB_DTN.ilike(f"%{term}%") for term in search_terms])
            )

    # ── General advanced filters ──────────────────────────────────────────────
    if est_cat:
        query = query.filter(MainDB.DB_EST_CAT == est_cat)
    if app_type:
        query = query.filter(MainDB.DB_APP_TYPE == app_type)
    if lto_company:
        query = query.filter(MainDB.DB_EST_LTO_COMP.ilike(f"%{lto_company}%"))
    if brand_name:
        query = query.filter(MainDB.DB_PROD_BR_NAME.ilike(f"%{brand_name}%"))
    if generic_name:
        query = query.filter(MainDB.DB_PROD_GEN_NAME.ilike(f"%{generic_name}%"))
    if dosage_form:
        query = query.filter(MainDB.DB_PROD_DOS_FORM.ilike(f"%{dosage_form}%"))
    if doc_type:
        query = query.filter(MainDB.DB_TYPE_DOC_RELEASED == doc_type)
    if uploaded_by:
        query = query.filter(MainDB.DB_USER_UPLOADER.ilike(f"%{uploaded_by}%"))
    if upload_date_from:
        query = query.filter(func.date(MainDB.DB_DATE_EXCEL_UPLOAD) >= upload_date_from)
    if upload_date_to:
        query = query.filter(func.date(MainDB.DB_DATE_EXCEL_UPLOAD) <= upload_date_to)
    if date_received_from:
        query = query.filter(MainDB.DB_DATE_RECEIVED_CENT >= date_received_from)
    if date_received_to:
        query = query.filter(MainDB.DB_DATE_RECEIVED_CENT <= date_received_to)
    if date_released_from:
        query = query.filter(MainDB.DB_DATE_RELEASED >= date_released_from)
    if date_released_to:
        query = query.filter(MainDB.DB_DATE_RELEASED <= date_released_to)

    # ── Supply chain filters ──────────────────────────────────────────────────
    if manufacturer:
        query = query.filter(MainDB.DB_PROD_MANU.ilike(f"%{manufacturer}%"))
    if manufacturer_country:
        query = query.filter(MainDB.DB_PROD_MANU_COUNTRY == manufacturer_country)
    if trader:
        query = query.filter(MainDB.DB_PROD_TRADER.ilike(f"%{trader}%"))
    if trader_country:
        query = query.filter(MainDB.DB_PROD_TRADER_COUNTRY == trader_country)
    if importer:
        query = query.filter(MainDB.DB_PROD_IMPORTER.ilike(f"%{importer}%"))
    if importer_country:
        query = query.filter(MainDB.DB_PROD_IMPORTER_COUNTRY == importer_country)
    if distributor:
        query = query.filter(MainDB.DB_PROD_DISTRI.ilike(f"%{distributor}%"))
    if distributor_country:
        query = query.filter(MainDB.DB_PROD_DISTRI_COUNTRY == distributor_country)
    if repacker:
        query = query.filter(MainDB.DB_PROD_REPACKER.ilike(f"%{repacker}%"))
    if repacker_country:
        query = query.filter(MainDB.DB_PROD_REPACKER_COUNTRY == repacker_country)

    total = query.count()
    rows  = (
        query.order_by(desc(MainDB.DB_DATE_EXCEL_UPLOAD))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    data = [
        {
            "id":               r.DB_ID,
            "processing_type":  r.DB_PROCESSING_TYPE,
            "app_type":         r.DB_APP_TYPE,
            "app_status":       r.DB_APP_STATUS,
            "dtn":              str(r.DB_DTN) if r.DB_DTN else None,
            "category":         r.DB_PHARMA_PROD_CAT_LABEL or r.DB_PROD_CAT,
            "lto_company":      r.DB_EST_LTO_COMP,
            "lto_address":      getattr(r, "DB_EST_LTO_ADDRESS", None) or getattr(r, "DB_EST_LTO_ADD", None),
            "doc_type":         r.DB_TYPE_DOC_RELEASED,
            "date_released":    r.DB_DATE_RELEASED,
            "date_received":    r.DB_DATE_RECEIVED_CENT,
            # extra fields for advanced filter context
            "brand_name":       r.DB_PROD_BR_NAME,
            "generic_name":     r.DB_PROD_GEN_NAME,
            "dosage_form":      r.DB_PROD_DOS_FORM,
            "manufacturer":     r.DB_PROD_MANU,
            "manufacturer_country": r.DB_PROD_MANU_COUNTRY,
            "trader":           r.DB_PROD_TRADER,
            "trader_country":   r.DB_PROD_TRADER_COUNTRY,
            "importer":         r.DB_PROD_IMPORTER,
            "importer_country": r.DB_PROD_IMPORTER_COUNTRY,
            "distributor":      r.DB_PROD_DISTRI,
            "distributor_country": r.DB_PROD_DISTRI_COUNTRY,
            "repacker":         r.DB_PROD_REPACKER,
            "repacker_country": r.DB_PROD_REPACKER_COUNTRY,
            "uploaded_by":      r.DB_USER_UPLOADER,
            "upload_date":      str(r.DB_DATE_EXCEL_UPLOAD) if r.DB_DATE_EXCEL_UPLOAD else None,
        }
        for r in rows
    ]

    return {
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "data":        data,
    }
