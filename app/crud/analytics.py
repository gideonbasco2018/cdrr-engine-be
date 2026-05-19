# app/crud/analytics.py

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.main_db import MainDB

from sqlalchemy import case, func, Float, Integer, extract

MONTHS_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


# ── Helper: parse date safely ─────────────────────────────────
def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except Exception:
        return None


# ── Helper: classify record ───────────────────────────────────
def _classify(record):
    doc = (record.DB_TYPE_DOC_RELEASED or "").upper()
    status = (record.DB_APP_STATUS or "").upper()
    if "CPR" in doc:
        return "cpr"
    elif "NOD" in doc:
        return "nod"
    elif status == "ON-PROCESS":
        return "on_process"
    elif status == "COMPLETED":
        return "completed"
    return "other"


# ── Helper: apply year/month/prescription filters ─────────────
def _apply_filters(records, year="All", month="All", prescription="All"):
    result = []
    for r in records:
        if prescription != "All":
            if (r.DB_PROD_CLASS_PRESCRIP or "") != prescription:
                continue
        if year != "All":
            d = _parse_date(r.DB_DATE_RELEASED)
            if not d or d.year != int(year):
                continue
            if month != "All":
                if d.month != int(month) + 1:
                    continue
        result.append(r)
    return result


# ── 1. Available Years ────────────────────────────────────────
def get_analytics_available_years(db: Session) -> list:
    records = db.query(MainDB.DB_DATE_RELEASED).filter(
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
    ).all()

    years = set()
    for r in records:
        d = _parse_date(r.DB_DATE_RELEASED)
        if d:
            years.add(str(d.year))

    return ["All"] + sorted(years)


# ── 2. Stat Cards Summary ─────────────────────────────────────
def get_analytics_summary(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> dict:
    all_records = db.query(MainDB).all()
    records = _apply_filters(all_records, year, month, prescription)

    total = len(records)
    cpr = sum(1 for r in records if "CPR" in (r.DB_TYPE_DOC_RELEASED or "").upper())
    nod = sum(1 for r in records if "NOD" in (r.DB_TYPE_DOC_RELEASED or "").upper())
    on_process = sum(1 for r in records if (r.DB_APP_STATUS or "").upper() == "ON-PROCESS")
    completed = sum(1 for r in records if (r.DB_APP_STATUS or "").upper() == "COMPLETED")
    approval_rate = round((cpr / total * 100), 1) if total > 0 else 0.0

    return {
        "total": total,
        "cpr": cpr,
        "nod": nod,
        "on_process": on_process,
        "completed": completed,
        "approval_rate": approval_rate,
    }


# ── 3. Trend Chart ────────────────────────────────────────────
def get_analytics_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    all_records = db.query(MainDB).filter(
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
    ).all()

    records = _apply_filters(all_records, year, month, prescription)
    groups = {}

    for r in records:
        d = _parse_date(r.DB_DATE_RELEASED)
        if not d:
            continue

        key = str(d.year) if year == "All" else d.strftime("%b")

        if key not in groups:
            groups[key] = {
                "label": key,
                "cpr": 0,
                "nod": 0,
                "on_process": 0,
                "completed": 0,
            }

        category = _classify(r)
        if category in groups[key]:
            groups[key][category] += 1

    if year == "All":
        return sorted(groups.values(), key=lambda x: x["label"])
    else:
        return sorted(
            groups.values(),
            key=lambda x: MONTHS_ORDER.index(x["label"])
            if x["label"] in MONTHS_ORDER else 99,
        )


# ── 4. By Classification ──────────────────────────────────────
def get_analytics_by_classification(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    all_records = db.query(MainDB).filter(
        MainDB.DB_PROD_CLASS_PRESCRIP.isnot(None),
        MainDB.DB_PROD_CLASS_PRESCRIP != "",
    ).all()

    records = _apply_filters(all_records, year, month, prescription)
    groups = {}

    for r in records:
        rx = r.DB_PROD_CLASS_PRESCRIP
        if rx not in groups:
            groups[rx] = {"type": rx, "count": 0, "cpr": 0, "nod": 0}

        groups[rx]["count"] += 1
        doc = (r.DB_TYPE_DOC_RELEASED or "").upper()
        if "CPR" in doc:
            groups[rx]["cpr"] += 1
        elif "NOD" in doc:
            groups[rx]["nod"] += 1

    for g in groups.values():
        g["rate"] = round((g["cpr"] / g["count"] * 100), 1) if g["count"] > 0 else 0.0

    return sorted(groups.values(), key=lambda x: x["count"], reverse=True)


# ── 5. Year-by-Year Summary ───────────────────────────────────
def get_analytics_year_summary(db: Session) -> list:
    records = db.query(MainDB).filter(
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
    ).all()

    groups = {}
    for r in records:
        d = _parse_date(r.DB_DATE_RELEASED)
        if not d:
            continue

        year = str(d.year)
        if year not in groups:
            groups[year] = {
                "year": year,
                "total": 0,
                "cpr": 0,
                "nod": 0,
                "on_process": 0,
                "completed": 0,
            }

        groups[year]["total"] += 1
        category = _classify(r)
        if category in groups[year]:
            groups[year][category] += 1

    for g in groups.values():
        g["rate"] = round((g["cpr"] / g["total"] * 100), 1) if g["total"] > 0 else 0.0

    return sorted(groups.values(), key=lambda x: x["year"])


# ── 6. Top Drugs ──────────────────────────────────────────────
def get_analytics_top_drugs(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
    limit: int = 8,
) -> list:
    all_records = db.query(MainDB).filter(
        MainDB.DB_PROD_BR_NAME.isnot(None),
        MainDB.DB_PROD_BR_NAME != "",
    ).all()

    records = _apply_filters(all_records, year, month, prescription)
    groups = {}

    for r in records:
        name = r.DB_PROD_BR_NAME
        if name not in groups:
            groups[name] = {
                "name": name,
                "generic": r.DB_PROD_GEN_NAME or "",
                "rx": r.DB_PROD_CLASS_PRESCRIP or "",
                "total": 0,
                "cpr": 0,
                "nod": 0,
            }

        groups[name]["total"] += 1
        doc = (r.DB_TYPE_DOC_RELEASED or "").upper()
        if "CPR" in doc:
            groups[name]["cpr"] += 1
        elif "NOD" in doc:
            groups[name]["nod"] += 1

    for g in groups.values():
        g["rate"] = round((g["cpr"] / g["total"] * 100), 1) if g["total"] > 0 else 0.0

    return sorted(groups.values(), key=lambda x: x["total"], reverse=True)[:limit]


# ── 7. Top Countries ─────────────────────────────────────────
ENTITY_FIELD_MAP = {
    "mfr":          "DB_PROD_MANU_COUNTRY",
    "trader":       "DB_PROD_TRADER_COUNTRY",
    "importer":     "DB_PROD_IMPORTER_COUNTRY",
    "distributor":  "DB_PROD_DISTRI_COUNTRY",
    "repacker":     "DB_PROD_REPACKER_COUNTRY",
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
    field = getattr(MainDB, field_name)

    all_records = db.query(MainDB).filter(
        field.isnot(None),
        field != "",
    ).all()

    records = _apply_filters(all_records, year, month, prescription)
    groups = {}

    for r in records:
        country = getattr(r, field_name)
        if not country:
            continue

        if country not in groups:
            groups[country] = {
                "country": country,
                "count": 0,
                "cpr": 0,
                "nod": 0,
                "on_process": 0,
            }

        groups[country]["count"] += 1
        category = _classify(r)
        if category in groups[country]:
            groups[country][category] += 1

    return sorted(groups.values(), key=lambda x: x["count"], reverse=True)[:limit]



def get_analytics_frp_tat_trend(db: Session, year: str = "All", month: str = "All") -> list:
    """
    Computes average, min, max TAT (in days) for FRP and CRP applications
    grouped by quarter based on DB_DATE_RECEIVED_CENT.
    Supports optional year and month filtering.
    """

    month_col = func.month(MainDB.DB_DATE_RECEIVED_CENT)
    year_col = func.year(MainDB.DB_DATE_RECEIVED_CENT)

    quarter_label = case(
        (month_col.in_([7, 8, 9]),  func.concat('Sep ', year_col)),
        (month_col.in_([10, 11, 12]), func.concat('Dec ', year_col)),
        (month_col.in_([1, 2, 3]),  func.concat('Mar ', year_col)),
        (month_col.in_([4, 5, 6]),  func.concat('Jun ', year_col)),
        else_='Unknown'
    )

    quarter_sort = case(
        (month_col.in_([1, 2, 3]),   1),
        (month_col.in_([4, 5, 6]),   2),
        (month_col.in_([7, 8, 9]),   3),
        (month_col.in_([10, 11, 12]), 4),
        else_=5
    )

    tat_days = func.datediff(
        MainDB.DB_DATE_RELEASED,
        MainDB.DB_DATE_RECEIVED_CENT
    )

    query = (
        db.query(
            quarter_label.label("quarter"),
            year_col.label("year"),
            quarter_sort.label("quarter_sort"),
            func.count(MainDB.DB_ID).label("total_applications"),
            func.avg(tat_days).cast(Float).label("avg_tat_days"),
            func.min(tat_days).cast(Integer).label("min_tat_days"),
            func.max(tat_days).cast(Integer).label("max_tat_days"),
            func.min(MainDB.DB_TIMELINE_CITIZEN_CHARTER).label("target_days"),
        )
        .filter(
            MainDB.DB_PROCESSING_TYPE == "FRP and CRP",
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_TRASH.is_(None),
        )
    )

    # ── Optional Filters ──────────────────────────────────────────
    if year != "All":
        query = query.filter(year_col == int(year))

    if month != "All":
        query = query.filter(month_col == int(month))
    # ─────────────────────────────────────────────────────────────

    rows = (
        query
        .group_by("quarter", "year", "quarter_sort")
        .order_by("year", "quarter_sort")
        .all()
    )

    return [
        {
            "quarter": row.quarter,
            "total_applications": row.total_applications,
            "avg_tat_days": round(row.avg_tat_days, 2) if row.avg_tat_days else None,
            "min_tat_days": row.min_tat_days,
            "max_tat_days": row.max_tat_days,
            "target_days":  row.target_days, 
        }
        for row in rows
    ]