# app/crud/analytics.py
# from sqlalchemy.orm import Session
# from sqlalchemy import func, and_, extract
# from app.models.main_db import MainDB
# from datetime import datetime
# from typing import List


# def _build_date_filters(date_column, year: int, month: int | None, day: int | None):
#     """
#     Builds SQL filters for TEXT date fields using STR_TO_DATE
#     Expected format: YYYY-MM-DD (or compatible)
#     """
#     filters = [
#         func.year(func.str_to_date(date_column, "%Y-%m-%d")) == year
#     ]

#     if month:
#         filters.append(
#             func.month(func.str_to_date(date_column, "%Y-%m-%d")) == month
#         )

#     if day:
#         filters.append(
#             func.day(func.str_to_date(date_column, "%Y-%m-%d")) == day
#         )

#     return filters


# def count_received_fdac(
#     db: Session,
#     year: int,
#     month: int | None = None,
#     day: int | None = None,
# ) -> int:
#     filters = _build_date_filters(
#         MainDB.DB_DATE_RECEIVED_FDAC, year, month, day
#     )

#     return (
#         db.query(func.count(MainDB.DB_ID))
#         .filter(MainDB.DB_DATE_RECEIVED_FDAC.isnot(None))
#         .filter(*filters)
#         .scalar()
#         or 0
#     )


# def count_received_central(
#     db: Session,
#     year: int,
#     month: int | None = None,
#     day: int | None = None,
# ) -> int:
#     filters = _build_date_filters(
#         MainDB.DB_DATE_RECEIVED_CENT, year, month, day
#     )

#     return (
#         db.query(func.count(MainDB.DB_ID))
#         .filter(MainDB.DB_DATE_RECEIVED_CENT.isnot(None))
#         .filter(*filters)
#         .scalar()
#         or 0
#     )


# def get_monthly_breakdown(db: Session, year: int | None = None) -> List[dict]:
#     """
#     Get monthly breakdown of received applications (Jan-Dec)
#     If year is None, use current year
#     """
#     if year is None:
#         year = datetime.now().year
    
#     monthly_data = []
#     month_names = [
#         "January", "February", "March", "April", "May", "June",
#         "July", "August", "September", "October", "November", "December"
#     ]
    
#     for month_num in range(1, 13):
#         fdac_count = count_received_fdac(db=db, year=year, month=month_num)
#         central_count = count_received_central(db=db, year=year, month=month_num)
        
#         monthly_data.append({
#             "period": month_names[month_num - 1],
#             "month": month_num,
#             "year": year,
#             "fdac": fdac_count,
#             "central": central_count,
#             "total": fdac_count + central_count,
#         })
    
#     return monthly_data


# def get_yearly_breakdown(db: Session, num_years: int = 5) -> List[dict]:
#     """
#     Get yearly breakdown of received applications (last N years)
#     """
#     current_year = datetime.now().year
#     yearly_data = []
    
#     for year in range(current_year - num_years + 1, current_year + 1):
#         fdac_count = count_received_fdac(db=db, year=year)
#         central_count = count_received_central(db=db, year=year)
        
#         yearly_data.append({
#             "period": str(year),
#             "year": year,
#             "fdac": fdac_count,
#             "central": central_count,
#             "total": fdac_count + central_count,
#         })
    
#     return yearly_data

# NEW/5-15

# app/crud/analytics.py

from sqlalchemy.orm import Session
from datetime import datetime
from app.models.main_db import MainDB


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
