# app/crud/analytics.py

from sqlalchemy.orm import Session
from sqlalchemy import case, func, Float, Integer, literal, or_
from app.models.main_db import MainDB

MONTHS_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def _base_query(db, year="All", month="All", prescription="All"):
    q = db.query(MainDB)
    if prescription != "All":
        q = q.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    if year != "All":
        q = q.filter(func.substr(MainDB.DB_DATE_RELEASED, 1, 4) == str(year))
        if month != "All":
            month_num = str(int(month) + 1).zfill(2)
            q = q.filter(func.substr(MainDB.DB_DATE_RELEASED, 6, 2) == month_num)
    return q


def _cpr_case():
    return func.sum(case((MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%"), 1), else_=0))

def _lod_case():
    return func.sum(case((MainDB.DB_TYPE_DOC_RELEASED.ilike("%LOD%"), 1), else_=0))

def _on_process_case():
    return func.sum(case((MainDB.DB_APP_STATUS.ilike("ON-PROCESS"), 1), else_=0))

def _completed_case():
    return func.sum(case((MainDB.DB_APP_STATUS.ilike("COMPLETED"), 1), else_=0))

def _wd_diff(start_col, end_col):
    """
    Working days (Mon–Fri) between two MySQL date columns.

    Uses the lookup-table formula:
        5 * FLOOR(n / 7) + SUBSTR(lut, WEEKDAY(start)*7 + WEEKDAY(end) + 1, 1)

    MySQL WEEKDAY(): 0 = Monday … 6 = Sunday.
    Does NOT account for public holidays.
    """
    _LUT = literal("0123444401234443012345440123456601234566")
    n    = func.datediff(end_col, start_col)
    w1   = func.weekday(start_col)
    w2   = func.weekday(end_col)
    return (
        func.floor(n / 7) * 5
        + func.cast(func.substr(_LUT, w1 * 7 + w2 + 1, 1), Integer)
    )


# ── 1. Available Years ────────────────────────────────────────
def get_analytics_available_years(db: Session) -> list:
    rows = (
        db.query(func.substr(MainDB.DB_DATE_RELEASED, 1, 4).label("yr"))
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
        )
        .distinct()
        .all()
    )
    years = sorted({r.yr for r in rows if r.yr})
    return ["All"] + years


# ── 2. Stat Cards Summary ─────────────────────────────────────
def get_analytics_summary(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> dict:
    row = (
        _base_query(db, year, month, prescription)
        .with_entities(
            func.count(MainDB.DB_ID).label("total"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _on_process_case().label("on_process"),
            _completed_case().label("completed"),
        )
        .one()
    )
    total = row.total or 0
    cpr   = row.cpr   or 0
    return {
        "total":         total,
        "cpr":           cpr,
        "lod":           row.lod        or 0,
        "on_process":    row.on_process or 0,
        "completed":     row.completed  or 0,
        "approval_rate": round(cpr / total * 100, 1) if total else 0.0,
    }


# ── 3. Trend Chart ────────────────────────────────────────────
def get_analytics_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    if year == "All":
        group_expr = func.substr(MainDB.DB_DATE_RELEASED, 1, 4).label("grp")
    else:
        group_expr = func.substr(MainDB.DB_DATE_RELEASED, 6, 2).label("grp")

    rows = (
        _base_query(db, year, month, prescription)
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
        )
        .with_entities(
            group_expr,
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _on_process_case().label("on_process"),
            _completed_case().label("completed"),
        )
        .group_by("grp")
        .all()
    )

    result = []
    for r in rows:
        if year == "All":
            label, sort_key = r.grp, r.grp
        else:
            label    = MONTH_ABBR.get(int(r.grp), r.grp)
            sort_key = int(r.grp)
        result.append({
            "label":      label,
            "cpr":        r.cpr        or 0,
            "lod":        r.lod        or 0,
            "on_process": r.on_process or 0,
            "completed":  r.completed  or 0,
            "_s":         sort_key,
        })

    result.sort(key=lambda x: x.pop("_s"))
    return result


# ── 4. By Classification ──────────────────────────────────────
def get_analytics_by_classification(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    rows = (
        _base_query(db, year, month, prescription)
        .filter(
            MainDB.DB_PROD_CLASS_PRESCRIP.isnot(None),
            MainDB.DB_PROD_CLASS_PRESCRIP != "",
        )
        .with_entities(
            MainDB.DB_PROD_CLASS_PRESCRIP.label("rx"),
            func.count(MainDB.DB_ID).label("count"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
        )
        .group_by(MainDB.DB_PROD_CLASS_PRESCRIP)
        .order_by(func.count(MainDB.DB_ID).desc())
        .all()
    )
    result = []
    for r in rows:
        count = r.count or 0
        cpr   = r.cpr   or 0
        result.append({
            "type":  r.rx,
            "count": count,
            "cpr":   cpr,
            "lod":   r.lod or 0,
            "rate":  round(cpr / count * 100, 1) if count else 0.0,
        })
    return result


# ── 5. Year-by-Year Summary ───────────────────────────────────
def get_analytics_year_summary(db: Session) -> list:
    rows = (
        db.query(
            func.substr(MainDB.DB_DATE_RELEASED, 1, 4).label("yr"),
            func.count(MainDB.DB_ID).label("total"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _on_process_case().label("on_process"),
            _completed_case().label("completed"),
        )
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
        )
        .group_by("yr")
        .order_by("yr")
        .all()
    )
    result = []
    for r in rows:
        total = r.total or 0
        cpr   = r.cpr   or 0
        result.append({
            "year":       r.yr,
            "total":      total,
            "cpr":        cpr,
            "lod":        r.lod        or 0,
            "on_process": r.on_process or 0,
            "completed":  r.completed  or 0,
            "rate":       round(cpr / total * 100, 1) if total else 0.0,
        })
    return result


# ── 6. Top Drugs ──────────────────────────────────────────────
def get_analytics_top_drugs(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
    limit: int = 8,
) -> list:
    rows = (
        _base_query(db, year, month, prescription)
        .filter(
            MainDB.DB_PROD_BR_NAME.isnot(None),
            MainDB.DB_PROD_BR_NAME != "",
        )
        .with_entities(
            MainDB.DB_PROD_BR_NAME.label("name"),
            func.min(MainDB.DB_PROD_GEN_NAME).label("generic"),
            func.min(MainDB.DB_PROD_CLASS_PRESCRIP).label("rx"),
            func.count(MainDB.DB_ID).label("total"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
        )
        .group_by(MainDB.DB_PROD_BR_NAME)
        .order_by(func.count(MainDB.DB_ID).desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in rows:
        total = r.total or 0
        cpr   = r.cpr   or 0
        result.append({
            "name":    r.name,
            "generic": r.generic or "",
            "rx":      r.rx      or "",
            "total":   total,
            "cpr":     cpr,
            "lod":     r.lod or 0,
            "rate":    round(cpr / total * 100, 1) if total else 0.0,
        })
    return result


# ── 7. Top Countries ─────────────────────────────────────────
ENTITY_FIELD_MAP = {
    "mfr":         "DB_PROD_MANU_COUNTRY",
    "trader":      "DB_PROD_TRADER_COUNTRY",
    "importer":    "DB_PROD_IMPORTER_COUNTRY",
    "distributor": "DB_PROD_DISTRI_COUNTRY",
    "repacker":    "DB_PROD_REPACKER_COUNTRY",
}

def get_analytics_top_countries(
    db: Session,
    entity_type: str = "mfr",
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
    limit: int = 10,
) -> list:
    field_name = ENTITY_FIELD_MAP.get(entity_type, "DB_PROD_MANU_COUNTRY")
    field      = getattr(MainDB, field_name)

    rows = (
        _base_query(db, year, month, prescription)
        .filter(field.isnot(None), field != "")
        .with_entities(
            field.label("country"),
            func.count(MainDB.DB_ID).label("count"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _on_process_case().label("on_process"),
        )
        .group_by(field)
        .order_by(func.count(MainDB.DB_ID).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "country":    r.country,
            "count":      r.count      or 0,
            "cpr":        r.cpr        or 0,
            "lod":        r.lod        or 0,
            "on_process": r.on_process or 0,
        }
        for r in rows
    ]


# ── 8. FRP & CRP — TAT Trend (per month, grouped by timeline) ────────────────

MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def get_analytics_frp_tat_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
) -> list:
    """
    Returns avg/min/max working-day TAT per calendar month, split by
    DB_TIMELINE_CITIZEN_CHARTER so the frontend can render a separate tab
    for each target-day group (30-day, 45-day, 65-day tracks).

    Filters:
    - year  : "2025", "2026", … or "All"
    - month : "1"–"12"          or "All"
    """

    month_col = func.month(MainDB.DB_DATE_RECEIVED_CENT)
    year_col  = func.year(MainDB.DB_DATE_RECEIVED_CENT)

    tat_days = _wd_diff(
        MainDB.DB_DATE_RECEIVED_CENT,
        MainDB.DB_DATE_RELEASED,
    )

    query = (
        db.query(
            year_col.label("year"),
            month_col.label("month_num"),
            MainDB.DB_TIMELINE_CITIZEN_CHARTER.label("timeline_days"),
            func.count(MainDB.DB_ID).label("total_applications"),
            func.avg(tat_days).cast(Float).label("avg_tat_days"),
            func.min(tat_days).cast(Integer).label("min_tat_days"),
            func.max(tat_days).cast(Integer).label("max_tat_days"),
        )
        .filter(
            MainDB.DB_PROCESSING_TYPE == "FRP and CRP",
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_TRASH.is_(None),
            MainDB.DB_APP_STATUS == "COMPLETED",
        )
    )

    if year != "All":
        query = query.filter(year_col == int(year))

    if month != "All":
        query = query.filter(month_col == int(month))

    rows = (
        query
        .group_by("year", "month_num", "timeline_days")
        .order_by("timeline_days", "year", "month_num")
        .all()
    )

    return [
        {
            "month":              f"{MONTH_ABBR[row.month_num - 1]} {row.year}",
            "year":               row.year,
            "month_num":          row.month_num,
            "timeline_days":      row.timeline_days,
            "total_applications": row.total_applications,
            "avg_tat_days":       round(row.avg_tat_days, 2) if row.avg_tat_days is not None else None,
            "min_tat_days":       row.min_tat_days,
            "max_tat_days":       row.max_tat_days,
        }
        for row in rows
    ]


# ── 9. FRP & CRP — TAT Outliers ──────────────────────────────────────────────

def get_analytics_frp_tat_outliers(
    db: Session,
    extreme_threshold: int = 365,
) -> dict:
    """
    Returns FRP and CRP records with:
    - Negative TAT  (released before received — data-entry error)
    - Extreme TAT   (working days > extreme_threshold)
    """

    tat_days = _wd_diff(
        MainDB.DB_DATE_RECEIVED_CENT,
        MainDB.DB_DATE_RELEASED,
    )

    rows = (
        db.query(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_DATE_RECEIVED_CENT,
            MainDB.DB_DATE_RELEASED,
            MainDB.DB_EST_LTO_COMP,
            tat_days.label("tat_days"),
        )
        .filter(
            MainDB.DB_PROCESSING_TYPE == "FRP and CRP",
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_TRASH.is_(None),
            MainDB.DB_APP_STATUS == "COMPLETED",
            or_(
                tat_days < 0,
                tat_days > extreme_threshold,
            ),
        )
        .order_by(tat_days)   # negative first, then extreme
        .all()
    )

    result = []
    for row in rows:
        quarter = None
        if row.DB_DATE_RECEIVED_CENT:
            try:
                from datetime import datetime
                d = datetime.strptime(str(row.DB_DATE_RECEIVED_CENT), "%Y-%m-%d")
                m, y = d.month, d.year
                if m in [7, 8, 9]:     quarter = f"Sep {y}"
                elif m in [10, 11, 12]: quarter = f"Dec {y}"
                elif m in [1, 2, 3]:   quarter = f"Mar {y}"
                else:                   quarter = f"Jun {y}"
            except Exception:
                pass

        issue = "negative_tat" if (row.tat_days or 0) < 0 else "extreme_tat"

        result.append({
            "db_id":              row.DB_ID,
            "dtn":                str(row.DB_DTN) if row.DB_DTN else None,
            "quarter":            quarter,
            "date_received_cent": str(row.DB_DATE_RECEIVED_CENT) if row.DB_DATE_RECEIVED_CENT else None,
            "date_released":      str(row.DB_DATE_RELEASED)      if row.DB_DATE_RELEASED      else None,
            "tat_days":           row.tat_days,
            "est_company":        row.DB_EST_LTO_COMP,
            "issue":              issue,
        })

    return {
        "total":    len(result),
        "negative": sum(1 for r in result if r["issue"] == "negative_tat"),
        "extreme":  sum(1 for r in result if r["issue"] == "extreme_tat"),
        "data":     result,
    }