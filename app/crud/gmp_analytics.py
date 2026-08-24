# app/crud/gmp_analytics.py

import re
from collections import Counter
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import case, func, Float, Integer, literal, text
from app.models.gmp_record import GMPRecord, GMPApplicationLogs
from app.crud.gmp_record import GMP_LOG_STEPS, GMP_TERMINAL_STATUSES


MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

STEP_ORDER = [label for label, _ in GMP_LOG_STEPS]

# Snapshot of PIC/S participating authorities' countries/entities from
# https://picscheme.org/en/members (checked 2026-08-17). Changes rarely, but
# should be re-checked against the live site periodically.
PICS_MEMBER_COUNTRIES = [
    "Argentina", "Australia", "Austria", "Belgium", "Brazil", "Bulgaria",
    "Canada", "Chinese Taipei", "Croatia", "Cyprus", "Czech Republic",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hong Kong", "Hungary", "Iceland", "Indonesia", "Iran", "Ireland",
    "Israel", "Italy", "Japan", "Jordan", "Korea, Republic of", "Latvia",
    "Liechtenstein", "Lithuania", "Malaysia", "Malta", "Mexico",
    "Netherlands", "New Zealand", "Norway", "Poland", "Portugal",
    "Romania", "Saudi Arabia", "Singapore", "Slovak Republic", "Slovenia",
    "South Africa", "Spain", "Sweden", "Switzerland", "Thailand",
    "Türkiye", "Ukraine", "United Kingdom", "United States",
]

# Free-text aliases -> canonical PIC/S member name, used to best-effort
# match GMP_FOREIGN_MANUFACTURER_ADDRESS (a free-text field with no
# separate country column) against the roster above.
_PICS_COUNTRY_ALIASES: Dict[str, str] = {
    "south korea": "Korea, Republic of",
    "republic of korea": "Korea, Republic of",
    "korea": "Korea, Republic of",
    "taiwan": "Chinese Taipei",
    "czechia": "Czech Republic",
    "slovakia": "Slovak Republic",
    "turkiye": "Türkiye",
    "turkey": "Türkiye",
    "united states of america": "United States",
    "usa": "United States",
    "u.s.a.": "United States",
    "great britain": "United Kingdom",
    "uk": "United Kingdom",
    **{c.lower(): c for c in PICS_MEMBER_COUNTRIES},
}
# Longest alias first, so e.g. "korea, republic of" is tried before "korea".
_PICS_ALIASES_BY_LENGTH = sorted(_PICS_COUNTRY_ALIASES.items(), key=lambda kv: -len(kv[0]))


def _match_pics_country(address: str):
    """Best-effort: returns the canonical PIC/S member country name found in
    a free-text manufacturer address, or None if no member country matched.
    Heuristic, not authoritative — absence of a match doesn't prove the
    manufacturer isn't in a PIC/S country, only that this parser didn't find it.
    """
    if not address:
        return None
    addr_low = address.lower()
    for alias, canonical in _PICS_ALIASES_BY_LENGTH:
        if re.search(r"\b" + re.escape(alias) + r"\b", addr_low):
            return canonical
    return None


def _base_query(db, year="All", month="All", est_category="All"):
    q = db.query(GMPRecord).filter(GMPRecord.GMP_TRASH.is_(None))
    if est_category != "All":
        q = q.filter(GMPRecord.GMP_EST_CATEGORY == est_category)
    if year != "All":
        q = q.filter(func.year(GMPRecord.GMP_DATE_RECEIVED) == int(year))
        if month != "All":
            q = q.filter(func.month(GMPRecord.GMP_DATE_RECEIVED) == int(month))
    return q


def _released_case():
    return func.sum(case((func.upper(GMPRecord.GMP_APP_STATUS).in_(["RELEASED", "COMPLETED"]), 1), else_=0))

def _disapproved_case():
    return func.sum(case((func.upper(GMPRecord.GMP_APP_STATUS) == "DISAPPROVED", 1), else_=0))

def _on_process_case():
    # GMP_APP_STATUS is routinely blank/NULL while a record is actively moving
    # (see gmp_record.py's _effective_status_col comment). coalesce() to ""
    # before the IN check keeps the NOT(...) two-valued instead of NULL, so
    # ANDing with has_current_step doesn't silently drop those blank-status
    # in-progress records into the else=0 branch.
    has_current_step = GMPRecord.GMP_CURRENT_STEP.isnot(None) & (GMPRecord.GMP_CURRENT_STEP != "")
    is_terminal = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, "")).in_(
        [s.upper() for s in GMP_TERMINAL_STATUSES]
    )
    return func.sum(case((~is_terminal & has_current_step, 1), else_=0))

def _wd_diff(start_col, end_col):
    # 49-char lookup table (7x7, indexed by WEEKDAY(start)*7 + WEEKDAY(end)),
    # brute-force verified against real date arithmetic — the previous
    # 40-char string silently returned 0 (via SUBSTR() -> '' -> CAST 0) for
    # any pair where WEEKDAY(start) was Saturday(5)/Sunday(6), undercounting
    # working days whenever GMP_DATE_RECEIVED fell on a weekend.
    _LUT = literal("0123444401233334012222340111123400012345001234550")
    n    = func.datediff(end_col, start_col)
    w1   = func.weekday(start_col)
    w2   = func.weekday(end_col)
    return (
        func.floor(n / 7) * 5
        + func.cast(func.substr(_LUT, w1 * 7 + w2 + 1, 1), Integer)
    )


# ── 1. Available Years ────────────────────────────────────────
def get_gmp_analytics_available_years(db: Session) -> list:
    year_col = func.year(GMPRecord.GMP_DATE_RECEIVED)
    rows = (
        db.query(year_col.label("yr"))
        .filter(
            GMPRecord.GMP_TRASH.is_(None),
            GMPRecord.GMP_DATE_RECEIVED.isnot(None),
        )
        .distinct()
        .all()
    )
    years = sorted({r.yr for r in rows if r.yr})
    return ["All"] + [str(y) for y in years]


# ── 2. Summary KPIs ────────────────────────────────────────────
def get_gmp_analytics_summary(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> dict:
    row = (
        _base_query(db, year, month, est_category)
        .with_entities(
            func.count(GMPRecord.GMP_ID).label("total"),
            _released_case().label("released"),
            _on_process_case().label("on_process"),
            _disapproved_case().label("disapproved"),
        )
        .one()
    )
    total = int(row.total or 0)
    released = int(row.released or 0)

    tat_days = _wd_diff(GMPRecord.GMP_DATE_RECEIVED, GMPRecord.GMP_RELEASED_DATE)
    tat_row = (
        _base_query(db, year, month, est_category)
        .filter(
            GMPRecord.GMP_DATE_RECEIVED.isnot(None),
            GMPRecord.GMP_RELEASED_DATE.isnot(None),
        )
        .with_entities(func.avg(tat_days).cast(Float).label("avg_tat"))
        .one()
    )

    return {
        "total":         total,
        "released":      released,
        "on_process":    int(row.on_process   or 0),
        "disapproved":   int(row.disapproved  or 0),
        "avg_tat_days":  round(tat_row.avg_tat, 2) if tat_row.avg_tat is not None else None,
        "release_rate":  round(released / total * 100, 1) if total else 0.0,
    }


# ── 2b. DTN-level rollup ─────────────────────────────────────────
# One GMP_DTN can have several GMP_REFERENCE_NO rows (different
# GMP_TYPE_OF_ISSUANCE, e.g. a Certificate + a later NFI sharing the same
# DTN) — each with its own status. The reference-level summary above counts
# every issuance row independently, which is correct for "how many issuances
# are done" but doesn't answer "is this application (DTN) done" when one of
# its issuances is released while another is still moving. A DTN only counts
# as Completed once ALL of its reference rows are terminal; if any row is
# still open the whole DTN counts as On Process.
def get_gmp_analytics_dtn_summary(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> dict:
    status_upper = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, ""))
    is_terminal = status_upper.in_([s.upper() for s in GMP_TERMINAL_STATUSES])
    is_disapproved = status_upper == "DISAPPROVED"
    is_open = ~is_terminal

    # Records without a DTN can't be grouped with anything else — fold each
    # one into its own single-row group instead of collapsing them all under
    # a shared NULL key.
    dtn_key = func.coalesce(GMPRecord.GMP_DTN, -GMPRecord.GMP_ID)

    rows = (
        _base_query(db, year, month, est_category)
        .with_entities(
            dtn_key.label("dtn_key"),
            func.count(GMPRecord.GMP_ID).label("ref_count"),
            func.sum(case((is_open, 1), else_=0)).label("open_count"),
            func.sum(case((is_disapproved, 1), else_=0)).label("disapproved_count"),
        )
        .group_by("dtn_key")
        .all()
    )

    total_dtns = len(rows)
    on_process = sum(1 for r in rows if r.open_count > 0)
    disapproved = sum(1 for r in rows if r.open_count == 0 and r.disapproved_count > 0)
    completed = total_dtns - on_process - disapproved

    # How many issuance (reference) records share the same DTN — e.g. a DTN
    # with a Certificate + a later NFI sharing that DTN counts as 2.
    MAX_BUCKET = 4
    issuance_counts = Counter(min(r.ref_count, MAX_BUCKET) for r in rows)
    issuance_count_distribution = [
        {
            "label": f"{n}+ issuance{'s' if n != 1 else ''}" if n == MAX_BUCKET else f"{n} issuance{'s' if n != 1 else ''}",
            "count": issuance_counts.get(n, 0),
        }
        for n in range(1, MAX_BUCKET + 1)
    ]

    return {
        "total_dtns":          total_dtns,
        "completed":           completed,
        "on_process":          on_process,
        "disapproved":         disapproved,
        "multi_issuance_dtns": sum(1 for r in rows if r.ref_count > 1),
        "issuance_count_distribution": issuance_count_distribution,
    }


# ── 3. Trend (received vs released) ────────────────────────────
def get_gmp_analytics_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> list:
    if year == "All":
        group_expr = func.year(GMPRecord.GMP_DATE_RECEIVED).label("grp")
    else:
        group_expr = func.month(GMPRecord.GMP_DATE_RECEIVED).label("grp")

    rows = (
        _base_query(db, year, month, est_category)
        .filter(GMPRecord.GMP_DATE_RECEIVED.isnot(None))
        .with_entities(
            group_expr,
            func.count(GMPRecord.GMP_ID).label("received"),
            _released_case().label("released"),
            _disapproved_case().label("disapproved"),
        )
        .group_by("grp")
        .all()
    )

    result = []
    for r in rows:
        if r.grp is None:
            continue
        if year == "All":
            label, sort_key = str(r.grp), r.grp
        else:
            label    = MONTH_ABBR.get(int(r.grp), str(r.grp))
            sort_key = int(r.grp)
        result.append({
            "label":      label,
            "received":   int(r.received    or 0),
            "released":   int(r.released    or 0),
            "disapproved": int(r.disapproved or 0),
            "_s":         sort_key,
        })

    result.sort(key=lambda x: x.pop("_s"))
    return result


# ── 4. By Category ──────────────────────────────────────────────
def get_gmp_analytics_by_category(
    db: Session,
    year: str = "All",
    month: str = "All",
    limit: int = 10,
) -> dict:
    by_est_category = (
        _base_query(db, year, month)
        .filter(GMPRecord.GMP_EST_CATEGORY.isnot(None), GMPRecord.GMP_EST_CATEGORY != "")
        .with_entities(
            GMPRecord.GMP_EST_CATEGORY.label("name"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_EST_CATEGORY)
        .order_by(func.count(GMPRecord.GMP_ID).desc())
        .all()
    )

    by_pics_nonpics = (
        _base_query(db, year, month)
        .filter(GMPRecord.GMP_PICS_NONPICS.isnot(None), GMPRecord.GMP_PICS_NONPICS != "")
        .with_entities(
            GMPRecord.GMP_PICS_NONPICS.label("name"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_PICS_NONPICS)
        .order_by(func.count(GMPRecord.GMP_ID).desc())
        .all()
    )

    top_companies = (
        _base_query(db, year, month)
        .filter(GMPRecord.GMP_LTO_COMPANY.isnot(None), GMPRecord.GMP_LTO_COMPANY != "")
        .with_entities(
            GMPRecord.GMP_LTO_COMPANY.label("name"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_LTO_COMPANY)
        .order_by(func.count(GMPRecord.GMP_ID).desc())
        .limit(limit)
        .all()
    )

    by_issuance_type = (
        _base_query(db, year, month)
        .filter(GMPRecord.GMP_TYPE_OF_ISSUANCE.isnot(None), GMPRecord.GMP_TYPE_OF_ISSUANCE != "")
        .with_entities(
            GMPRecord.GMP_TYPE_OF_ISSUANCE.label("name"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_TYPE_OF_ISSUANCE)
        .order_by(func.count(GMPRecord.GMP_ID).desc())
        .all()
    )

    by_transaction_type = (
        _base_query(db, year, month)
        .filter(GMPRecord.GMP_TRANSACTION_TYPE.isnot(None), GMPRecord.GMP_TRANSACTION_TYPE != "")
        .with_entities(
            GMPRecord.GMP_TRANSACTION_TYPE.label("name"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_TRANSACTION_TYPE)
        .order_by(func.count(GMPRecord.GMP_ID).desc())
        .all()
    )

    by_product_line = (
        _base_query(db, year, month)
        .filter(GMPRecord.GMP_PRODUCT_LINE.isnot(None), GMPRecord.GMP_PRODUCT_LINE != "")
        .with_entities(
            GMPRecord.GMP_PRODUCT_LINE.label("name"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_PRODUCT_LINE)
        .order_by(func.count(GMPRecord.GMP_ID).desc())
        .limit(limit)
        .all()
    )

    return {
        "by_est_category":     [{"name": r.name, "count": int(r.count or 0)} for r in by_est_category],
        "by_pics_nonpics":     [{"name": r.name, "count": int(r.count or 0)} for r in by_pics_nonpics],
        "top_companies":       [{"name": r.name, "count": int(r.count or 0)} for r in top_companies],
        "by_issuance_type":    [{"name": r.name, "count": int(r.count or 0)} for r in by_issuance_type],
        "by_transaction_type": [{"name": r.name, "count": int(r.count or 0)} for r in by_transaction_type],
        "by_product_line":     [{"name": r.name, "count": int(r.count or 0)} for r in by_product_line],
    }


# ── 5. Workflow Step Timing ─────────────────────────────────────
def get_gmp_analytics_step_timing(db: Session) -> list:
    duration = func.timestampdiff(text("DAY"), GMPApplicationLogs.start_date, GMPApplicationLogs.accomplished_date)

    rows = (
        db.query(
            GMPApplicationLogs.application_step.label("step"),
            func.count(GMPApplicationLogs.id).label("total"),
            func.avg(duration).cast(Float).label("avg_days"),
            func.min(duration).cast(Integer).label("min_days"),
            func.max(duration).cast(Integer).label("max_days"),
        )
        .filter(
            GMPApplicationLogs.application_status == "COMPLETED",
            GMPApplicationLogs.start_date.isnot(None),
            GMPApplicationLogs.accomplished_date.isnot(None),
        )
        .group_by(GMPApplicationLogs.application_step)
        .all()
    )

    by_step = {r.step: r for r in rows}
    result = []
    for step in STEP_ORDER:
        r = by_step.get(step)
        if r is None:
            continue
        result.append({
            "step":      step,
            "total":     int(r.total or 0),
            "avg_days":  round(r.avg_days, 2) if r.avg_days is not None else None,
            "min_days":  r.min_days,
            "max_days":  r.max_days,
        })
    return result


# ── 6. Evaluator workload ───────────────────────────────────────
def get_gmp_analytics_workload(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
    limit: int = 15,
) -> list:
    """Open (non-terminal, actively-stepped) task count and avg TAT per assigned evaluator."""
    has_current_step = GMPRecord.GMP_CURRENT_STEP.isnot(None) & (GMPRecord.GMP_CURRENT_STEP != "")
    is_terminal = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, "")).in_(
        [s.upper() for s in GMP_TERMINAL_STATUSES]
    )
    is_open = ~is_terminal & has_current_step

    tat_days = _wd_diff(GMPRecord.GMP_DATE_RECEIVED, GMPRecord.GMP_RELEASED_DATE)
    has_tat = GMPRecord.GMP_DATE_RECEIVED.isnot(None) & GMPRecord.GMP_RELEASED_DATE.isnot(None)

    rows = (
        _base_query(db, year, month, est_category)
        .filter(GMPRecord.GMP_EVALUATOR.isnot(None), GMPRecord.GMP_EVALUATOR != "")
        .with_entities(
            GMPRecord.GMP_EVALUATOR.label("evaluator"),
            func.sum(case((is_open, 1), else_=0)).label("open_count"),
            func.avg(case((has_tat, tat_days))).cast(Float).label("avg_tat"),
        )
        .group_by(GMPRecord.GMP_EVALUATOR)
        .order_by(func.sum(case((is_open, 1), else_=0)).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "evaluator":    r.evaluator,
            "open_count":   int(r.open_count or 0),
            "avg_tat_days": round(r.avg_tat, 2) if r.avg_tat is not None else None,
        }
        for r in rows
    ]


# ── 7. Backlog aging ─────────────────────────────────────────────
def get_gmp_analytics_aging(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> list:
    """
    Buckets currently On Process records by calendar days elapsed since
    GMP_DATE_RECEIVED — surfaces stale applications that the single
    "On Process" total hides.
    """
    has_current_step = GMPRecord.GMP_CURRENT_STEP.isnot(None) & (GMPRecord.GMP_CURRENT_STEP != "")
    is_terminal = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, "")).in_(
        [s.upper() for s in GMP_TERMINAL_STATUSES]
    )
    is_open = ~is_terminal & has_current_step

    days_open = func.datediff(func.curdate(), GMPRecord.GMP_DATE_RECEIVED)

    row = (
        _base_query(db, year, month, est_category)
        .filter(is_open, GMPRecord.GMP_DATE_RECEIVED.isnot(None))
        .with_entities(
            func.sum(case((days_open <= 5, 1), else_=0)).label("b0_5"),
            func.sum(case((days_open.between(6, 10), 1), else_=0)).label("b6_10"),
            func.sum(case((days_open.between(11, 20), 1), else_=0)).label("b11_20"),
            func.sum(case((days_open > 20, 1), else_=0)).label("b20plus"),
        )
        .one()
    )

    return [
        {"label": "0-5 days",   "count": int(row.b0_5 or 0)},
        {"label": "6-10 days",  "count": int(row.b6_10 or 0)},
        {"label": "11-20 days", "count": int(row.b11_20 or 0)},
        {"label": "20+ days",   "count": int(row.b20plus or 0)},
    ]


# ── 8. NOD (Notice of Deficiency) monitoring & compliance turnaround ─────────
def get_gmp_analytics_nod(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> dict:
    """
    How often applications need a Notice of Deficiency, and how long
    applicants take to respond with compliance docs afterward.

    NOD count per record = number of populated GMP_NOD_DATE_1..5 slots.
    "Last NOD date" assumes the 5 slots are filled in order (1st, 2nd, ...)
    without gaps, matching their column names — so the highest-numbered
    populated slot is the most recent notice.
    """
    nod_cols = [
        GMPRecord.GMP_NOD_DATE_1, GMPRecord.GMP_NOD_DATE_2, GMPRecord.GMP_NOD_DATE_3,
        GMPRecord.GMP_NOD_DATE_4, GMPRecord.GMP_NOD_DATE_5,
    ]
    nod_count = sum(case((col.isnot(None), 1), else_=0) for col in nod_cols)

    last_nod_date = case(
        (GMPRecord.GMP_NOD_DATE_5.isnot(None), GMPRecord.GMP_NOD_DATE_5),
        (GMPRecord.GMP_NOD_DATE_4.isnot(None), GMPRecord.GMP_NOD_DATE_4),
        (GMPRecord.GMP_NOD_DATE_3.isnot(None), GMPRecord.GMP_NOD_DATE_3),
        (GMPRecord.GMP_NOD_DATE_2.isnot(None), GMPRecord.GMP_NOD_DATE_2),
        (GMPRecord.GMP_NOD_DATE_1.isnot(None), GMPRecord.GMP_NOD_DATE_1),
        else_=None,
    )

    has_current_step = GMPRecord.GMP_CURRENT_STEP.isnot(None) & (GMPRecord.GMP_CURRENT_STEP != "")
    is_terminal = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, "")).in_(
        [s.upper() for s in GMP_TERMINAL_STATUSES]
    )
    is_open = ~is_terminal & has_current_step

    row = (
        _base_query(db, year, month, est_category)
        .with_entities(
            func.count(GMPRecord.GMP_ID).label("total"),
            func.sum(case((nod_count > 0, 1), else_=0)).label("with_nod"),
            func.avg(nod_count).cast(Float).label("avg_nod_count"),
            func.sum(case((nod_count == 0, 1), else_=0)).label("d0"),
            func.sum(case((nod_count == 1, 1), else_=0)).label("d1"),
            func.sum(case((nod_count == 2, 1), else_=0)).label("d2"),
            func.sum(case((nod_count == 3, 1), else_=0)).label("d3"),
            func.sum(case((nod_count == 4, 1), else_=0)).label("d4"),
            func.sum(case((nod_count == 5, 1), else_=0)).label("d5"),
            func.sum(case((
                (last_nod_date.isnot(None)) & (GMPRecord.GMP_COMPLIANCE_DOCS_DATE_RECEIVED.is_(None)) & is_open,
                1,
            ), else_=0)).label("pending_compliance"),
        )
        .one()
    )

    turnaround = func.datediff(GMPRecord.GMP_COMPLIANCE_DOCS_DATE_RECEIVED, last_nod_date)
    turnaround_row = (
        _base_query(db, year, month, est_category)
        .filter(last_nod_date.isnot(None), GMPRecord.GMP_COMPLIANCE_DOCS_DATE_RECEIVED.isnot(None))
        .with_entities(func.avg(turnaround).cast(Float).label("avg_turnaround"))
        .one()
    )

    total = int(row.total or 0)
    with_nod = int(row.with_nod or 0)

    return {
        "total_records":                  total,
        "records_with_nod":               with_nod,
        "nod_rate":                       round(with_nod / total * 100, 1) if total else 0.0,
        "avg_nod_count":                  round(row.avg_nod_count, 2) if row.avg_nod_count is not None else 0.0,
        "avg_compliance_turnaround_days": round(turnaround_row.avg_turnaround, 2) if turnaround_row.avg_turnaround is not None else None,
        "pending_compliance":             int(row.pending_compliance or 0),
        "distribution": [
            {"label": "0 NODs", "count": int(row.d0 or 0)},
            {"label": "1 NOD",  "count": int(row.d1 or 0)},
            {"label": "2 NODs", "count": int(row.d2 or 0)},
            {"label": "3 NODs", "count": int(row.d3 or 0)},
            {"label": "4 NODs", "count": int(row.d4 or 0)},
            {"label": "5 NODs", "count": int(row.d5 or 0)},
        ],
    }


# ── 9. PIC/S country breakdown & classification mismatches ───────────────────
def get_gmp_analytics_pics_country(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
    limit: int = 10,
    mismatch_limit: int = 25,
) -> dict:
    """
    Best-effort breakdown of the foreign manufacturer's country (parsed from
    GMP_FOREIGN_MANUFACTURER_ADDRESS against the PIC/S member roster), plus
    records whose GMP_PICS_NONPICS selection looks inconsistent with that
    detected country. Address parsing is heuristic — treat mismatches as
    "worth a second look", not confirmed data-entry errors.
    """
    rows = (
        _base_query(db, year, month, est_category)
        .filter(
            GMPRecord.GMP_FOREIGN_MANUFACTURER_ADDRESS.isnot(None),
            GMPRecord.GMP_FOREIGN_MANUFACTURER_ADDRESS != "",
        )
        .with_entities(
            GMPRecord.GMP_ID,
            GMPRecord.GMP_DTN,
            GMPRecord.GMP_REFERENCE_NO,
            GMPRecord.GMP_LTO_COMPANY,
            GMPRecord.GMP_FOREIGN_MANUFACTURER,
            GMPRecord.GMP_FOREIGN_MANUFACTURER_ADDRESS,
            GMPRecord.GMP_PICS_NONPICS,
        )
        .all()
    )

    OTHER = "Other / Not Detected"
    country_counts: Dict[str, int] = {}
    mismatches = []

    for r in rows:
        country = _match_pics_country(r.GMP_FOREIGN_MANUFACTURER_ADDRESS)
        key = country or OTHER
        country_counts[key] = country_counts.get(key, 0) + 1

        declared = (r.GMP_PICS_NONPICS or "").strip().upper()
        if declared not in ("PIC/S", "NON PIC/S"):
            continue  # skip blank / "LETTER and CORRECTION" / anything else

        is_member = country is not None
        if declared == "PIC/S" and not is_member:
            mismatches.append({
                "gmp_id":              r.GMP_ID,
                "dtn":                 str(r.GMP_DTN) if r.GMP_DTN is not None else None,
                "reference_no":        r.GMP_REFERENCE_NO,
                "company":             r.GMP_LTO_COMPANY,
                "foreign_manufacturer": r.GMP_FOREIGN_MANUFACTURER,
                "declared":            "PIC/S",
                "detected_country":    None,
                "reason":              "Declared PIC/S, but manufacturer address doesn't match a current PIC/S member country",
            })
        elif declared == "NON PIC/S" and is_member:
            mismatches.append({
                "gmp_id":              r.GMP_ID,
                "dtn":                 str(r.GMP_DTN) if r.GMP_DTN is not None else None,
                "reference_no":        r.GMP_REFERENCE_NO,
                "company":             r.GMP_LTO_COMPANY,
                "foreign_manufacturer": r.GMP_FOREIGN_MANUFACTURER,
                "declared":            "NON PIC/S",
                "detected_country":    country,
                "reason":              f"Declared Non-PIC/S, but manufacturer address matches {country}, a current PIC/S member",
            })

    by_country = sorted(
        ({"name": k, "count": v} for k, v in country_counts.items() if k != OTHER),
        key=lambda x: -x["count"],
    )[:limit]
    if country_counts.get(OTHER):
        by_country.append({"name": OTHER, "count": country_counts[OTHER]})

    return {
        "by_country":      by_country,
        "mismatch_count":  len(mismatches),
        "mismatches":      mismatches[:mismatch_limit],
    }
