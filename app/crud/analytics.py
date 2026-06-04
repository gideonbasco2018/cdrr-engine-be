# app/crud/analytics.py

from sqlalchemy.orm import Session
from sqlalchemy import case, func, Float, Integer, literal, or_
from app.models.main_db import MainDB


MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

def _base_query(db, year="All", month="All", prescription="All"):
    q = db.query(MainDB)
    if prescription != "All":
        q = q.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    if year != "All":
        q = q.filter(
            func.year(func.str_to_date(
                func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d"
            )) == int(year)
        )
        if month != "All":
            q = q.filter(
                func.month(func.str_to_date(
                    func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d"
                )) == int(month)
            )
    return q


def _cpr_case():
    return func.sum(case((MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%"), 1), else_=0))

def _lod_case():
    return func.sum(case((MainDB.DB_TYPE_DOC_RELEASED.ilike("%LOD%"), 1), else_=0))

def _on_process_case():
    return func.sum(case((
        or_(
            MainDB.DB_APP_STATUS.ilike("ON-PROCESS"),
            MainDB.DB_APP_STATUS.ilike("ON PROCESS"),
        ), 1), else_=0))

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
        db.query(
            func.year(func.str_to_date(
                func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d"
            )).label("yr")
        )
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
        )
        .distinct()
        .all()
    )
    years = sorted({r.yr for r in rows if r.yr})
    return ["All"] + [str(y) for y in years]


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
    total = int(row.total or 0)
    cpr   = int(row.cpr   or 0)
    return {
        "total":         total,
        "cpr":           cpr,
        "lod":           int(row.lod        or 0),
        "on_process":    int(row.on_process or 0),
        "completed":     int(row.completed  or 0),
        "approval_rate": round(cpr / total * 100, 1) if total else 0.0,
    }


# ── 3. Trend Chart ────────────────────────────────────────────
def get_analytics_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    date_col = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    if year == "All":
        group_expr = func.year(date_col).label("grp")
    else:
        group_expr = func.month(date_col).label("grp")

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
            label, sort_key = str(r.grp), r.grp
        else:
            label    = MONTH_ABBR.get(int(r.grp), str(r.grp))
            sort_key = int(r.grp)
        result.append({
            "label":      label,
            "cpr":        int(r.cpr        or 0),
            "lod":        int(r.lod        or 0),
            "on_process": int(r.on_process or 0),
            "completed":  int(r.completed  or 0),
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
        count = int(r.count or 0)
        cpr   = int(r.cpr   or 0)
        result.append({
            "type":  r.rx,
            "count": count,
            "cpr":   cpr,
            "lod":   int(r.lod or 0),
            "rate":  round(cpr / count * 100, 1) if count else 0.0,
        })
    return result


# ── 5. Year-by-Year Summary ───────────────────────────────────
def get_analytics_year_summary(db: Session) -> list:
    rows = (
        db.query(
            func.year(func.str_to_date(
                func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d"
            )).label("yr"),
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
        total = int(r.total or 0)
        cpr   = int(r.cpr   or 0)
        result.append({
            "year":       str(r.yr),
            "total":      total,
            "cpr":        cpr,
            "lod":        int(r.lod        or 0),
            "on_process": int(r.on_process or 0),
            "completed":  int(r.completed  or 0),
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
        total = int(r.total or 0)
        cpr   = int(r.cpr   or 0)
        result.append({
            "name":    r.name,
            "generic": r.generic or "",
            "rx":      r.rx      or "",
            "total":   total,
            "cpr":     cpr,
            "lod":     int(r.lod or 0),
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
            "count":      int(r.count      or 0),
            "cpr":        int(r.cpr        or 0),
            "lod":        int(r.lod        or 0),
            "on_process": int(r.on_process or 0),
        }
        for r in rows
    ]



def get_analytics_frp_tat_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
) -> list:
    clean_received = func.str_to_date(
        func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d"
    )
    clean_released = func.str_to_date(
        func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d"
    )
    month_col_received = func.month(clean_received)
    year_col_received  = func.year(clean_received)
    month_col_released = func.month(clean_released)
    year_col_released  = func.year(clean_released)

    tat_days = _wd_diff(clean_received, clean_released)
    query = (
        db.query(
            year_col_received.label("year_received"),
            month_col_received.label("month_num_received"),
            year_col_released.label("year_released"),
            month_col_released.label("month_num_released"),
            MainDB.DB_TIMELINE_CITIZEN_CHARTER.label("timeline_days"),
            MainDB.DB_TYPE_DOC_RELEASED.label("type_of_doc_released"),  # ← DAGDAG
            func.count(MainDB.DB_ID).label("total_applications"),
            func.avg(tat_days).cast(Float).label("avg_tat_days"),
            func.min(tat_days).cast(Integer).label("min_tat_days"),
            func.max(tat_days).cast(Integer).label("max_tat_days"),
        )
        .filter(
            MainDB.DB_PROCESSING_TYPE == "FRP and CRP",
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_DATE_RELEASED != "N/A",
            MainDB.DB_TRASH.is_(None),
            func.upper(MainDB.DB_APP_STATUS) == "COMPLETED",
            # Ensure str_to_date actually parses successfully (not NULL)
            clean_received.isnot(None),
            clean_released.isnot(None),
        )
    )

    if year != "All":
        query = query.filter(
            or_(
                year_col_received == int(year),
                year_col_released == int(year),
            )
        )
    if month != "All":
        query = query.filter(
            or_(
                month_col_received == int(month),
                month_col_released == int(month),
            )
        )

    rows = (
        query
        .group_by(
            "year_received", "month_num_received",
            "year_released", "month_num_released",
            "timeline_days", "type_of_doc_released"
        )
        .order_by("timeline_days", "year_received", "month_num_received")
        .all()
    )

    return [
        {
            # Received
            "month":                f"{MONTH_ABBR.get(row.month_num_received, str(row.month_num_received))} {row.year_received}",
            "year":                 row.year_received,
            "month_num":            row.month_num_received,
            # Released
            "month_released":       f"{MONTH_ABBR.get(row.month_num_released, str(row.month_num_released))} {row.year_released}",
            "year_released":        row.year_released,
            "month_num_released":   row.month_num_released,
            "timeline_days":        row.timeline_days,
            "type_of_doc_released": row.type_of_doc_released,
            "total_applications":   row.total_applications,
            "avg_tat_days":         round(row.avg_tat_days, 2) if row.avg_tat_days is not None else None,
            "min_tat_days":         row.min_tat_days,
            "max_tat_days":         row.max_tat_days,
        }
        for row in rows
        if row.year_received and row.month_num_received
        and row.year_released and row.month_num_released
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
        func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d"),
        func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d"),
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
            func.upper(MainDB.DB_APP_STATUS) == "COMPLETED",
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