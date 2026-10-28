# app/crud/gmp_analytics.py

import calendar
import re
from collections import Counter
from datetime import date, timedelta
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, case, func, Float, Integer, String, cast, literal, text
from app.models.gmp_record import GMPRecord, GMPApplicationLogs
from app.crud.gmp_record import GMP_LOG_STEPS, GMP_TERMINAL_STATUSES
from app.services.fgmp_claim import country_from_address


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
    # All years -> a point per year; one year -> per month; one month -> per day.
    by_day = year != "All" and month != "All"
    if year == "All":
        group_expr = func.year(GMPRecord.GMP_DATE_RECEIVED).label("grp")
    elif by_day:
        group_expr = func.day(GMPRecord.GMP_DATE_RECEIVED).label("grp")
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
            _on_process_case().label("on_process"),
        )
        .group_by("grp")
        .all()
    )

    if by_day:
        # Every day of the month, so quiet days show as 0 instead of vanishing.
        found = {int(r.grp): r for r in rows if r.grp is not None}
        abbr = MONTH_ABBR[int(month)]
        return [
            {
                "label":       f"{abbr} {d}",
                "received":    int(found[d].received    or 0) if d in found else 0,
                "released":    int(found[d].released    or 0) if d in found else 0,
                "disapproved": int(found[d].disapproved or 0) if d in found else 0,
                "on_process":  int(found[d].on_process  or 0) if d in found else 0,
            }
            for d in range(1, calendar.monthrange(int(year), int(month))[1] + 1)
        ]

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
            "on_process": int(r.on_process  or 0),
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
def _working_minutes(start, end) -> int:
    """Minutes between two datetimes with Saturdays and Sundays taken out, so a
    step that sits over a weekend isn't charged for it. Same weekday rule as
    _wd_diff (the Avg TAT tile): Monday-Friday, no holiday calendar. Exact to
    the minute, so a same-day hand-over still shows its hours, not 0."""
    if end <= start:
        return 0
    total = 0
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        nxt = day + timedelta(days=1)
        if day.weekday() < 5:
            total += int((min(end, nxt) - max(start, day)).total_seconds() // 60)
        day = nxt
    return total


def get_gmp_analytics_step_timing(db: Session) -> list:
    """Average WORKING time each workflow step took, from its log entries
    (start -> accomplished), finished entries only. Weekends excluded; values
    are returned in minutes (`*_minutes`) and in working days (`*_days`)."""
    rows = (
        db.query(
            GMPApplicationLogs.application_step,
            GMPApplicationLogs.start_date,
            GMPApplicationLogs.accomplished_date,
        )
        .filter(
            GMPApplicationLogs.application_status == "COMPLETED",
            GMPApplicationLogs.start_date.isnot(None),
            GMPApplicationLogs.accomplished_date.isnot(None),
        )
        .all()
    )

    durations: Dict[str, list] = {}
    for step, start, end in rows:
        durations.setdefault(step, []).append(_working_minutes(start, end))

    result = []
    for step in STEP_ORDER:
        d = durations.get(step)
        if not d:
            continue
        avg = sum(d) / len(d)
        result.append({
            "step":        step,
            "total":       len(d),
            "avg_days":    round(avg / 1440, 2),
            "min_days":    min(d) // 1440,
            "max_days":    max(d) // 1440,
            "avg_minutes": round(avg, 1),
            "min_minutes": min(d),
            "max_minutes": max(d),
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
    """Open (non-terminal, actively-stepped) task count and avg TAT per assigned evaluator.

    Reads the assigned evaluator from GMPApplicationLogs (each record's most
    recent "Evaluator"-step log), not GMPRecord.GMP_EVALUATOR. That column is
    only ever written by assign_evaluator() (app/crud/gmp_record.py), which
    the frontend only calls from one rare fallback branch — a record decked
    through the normal advance-step flow (the vast majority) never touches it
    at all, so grouping by it meant this widget was mostly empty. It also
    only stores a name, so even the few rows it *did* have would split into
    two buckets the moment that evaluator was renamed.
    GMPApplicationLogs.user_id, in contrast, is written for every record that
    ever reaches the Evaluator step — through advance_step, and through Excel
    import (GMP_LOG_STEPS_EXCEL has an Evaluator column) — and is stable
    across a rename, the same fix already applied to Tasks/Dashboard.
    """
    has_current_step = GMPRecord.GMP_CURRENT_STEP.isnot(None) & (GMPRecord.GMP_CURRENT_STEP != "")
    is_terminal = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, "")).in_(
        [s.upper() for s in GMP_TERMINAL_STATUSES]
    )
    is_open = ~is_terminal & has_current_step

    tat_days = _wd_diff(GMPRecord.GMP_DATE_RECEIVED, GMPRecord.GMP_RELEASED_DATE)
    has_tat = GMPRecord.GMP_DATE_RECEIVED.isnot(None) & GMPRecord.GMP_RELEASED_DATE.isnot(None)

    # Most recent "Evaluator"-step log per record — who's on record as the
    # evaluator, whether or not the application has since moved past them
    # (matches the old GMP_EVALUATOR semantics: it doesn't get cleared just
    # because the record advanced to Checker/QA Admin/etc.).
    rn = func.row_number().over(
        partition_by=GMPApplicationLogs.gmp_record_id,
        order_by=GMPApplicationLogs.del_index.desc(),
    ).label("rn")
    eval_logs = (
        db.query(
            GMPApplicationLogs.gmp_record_id.label("gmp_record_id"),
            GMPApplicationLogs.user_id.label("evaluator_user_id"),
            GMPApplicationLogs.user_name.label("evaluator_user_name"),
            rn,
        )
        .filter(GMPApplicationLogs.application_step == "Evaluator")
        .subquery()
    )
    latest_eval = db.query(eval_logs).filter(eval_logs.c.rn == 1).subquery()

    # Group by user_id when available (stable across a rename); only falls
    # back to the bare name for legacy logs that predate id tracking.
    evaluator_key = func.coalesce(
        cast(latest_eval.c.evaluator_user_id, String(20)), latest_eval.c.evaluator_user_name
    )

    rows = (
        _base_query(db, year, month, est_category)
        .join(latest_eval, latest_eval.c.gmp_record_id == GMPRecord.GMP_ID)
        .filter(evaluator_key.isnot(None))
        .with_entities(
            evaluator_key.label("eval_key"),
            # Representative display name for the group — arbitrary but
            # deterministic pick among that id's name variants; cosmetic only,
            # the grouping itself is what's keyed by the stable id.
            func.max(latest_eval.c.evaluator_user_name).label("evaluator"),
            func.sum(case((is_open, 1), else_=0)).label("open_count"),
            func.avg(case((has_tat, tat_days))).cast(Float).label("avg_tat"),
        )
        .group_by(evaluator_key)
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


# ── 6b. Applications by current step ─────────────────────────────
def get_gmp_analytics_by_step(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> list:
    """
    How many currently-open (non-terminal) applications are sitting at each
    workflow step right now — queue depth per step, so a pile-up at one
    specific step is visible instead of hiding inside one "On Process" total.
    """
    has_current_step = GMPRecord.GMP_CURRENT_STEP.isnot(None) & (GMPRecord.GMP_CURRENT_STEP != "")
    is_terminal = func.upper(func.coalesce(GMPRecord.GMP_APP_STATUS, "")).in_(
        [s.upper() for s in GMP_TERMINAL_STATUSES]
    )
    is_open = ~is_terminal & has_current_step

    rows = (
        _base_query(db, year, month, est_category)
        .filter(is_open)
        .with_entities(
            GMPRecord.GMP_CURRENT_STEP.label("step"),
            func.count(GMPRecord.GMP_ID).label("count"),
        )
        .group_by(GMPRecord.GMP_CURRENT_STEP)
        .all()
    )
    by_step = {r.step: int(r.count or 0) for r in rows}

    # Ordered by real workflow sequence (Decking → ... → OD Releasing), not
    # by count — this is a pipeline, and the order is the point (spot a
    # pile-up at a specific step at a glance). Steps with zero open
    # applications still appear, at 0, so the pipeline reads as complete.
    return [{"step": step, "count": by_step.get(step, 0)} for step in STEP_ORDER]


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
        # The bar chart names every country, not only PIC/S members. `country`
        # stays PIC/S-only: the mismatch check below depends on that.
        shown = country
        if not shown:
            other = country_from_address(r.GMP_FOREIGN_MANUFACTURER_ADDRESS)
            # Same spelling as the PIC/S list ("Taiwan" -> "Chinese Taipei"), so one country is never split in two bars.
            shown = _PICS_COUNTRY_ALIASES.get(other.lower(), other) if other else None
        key = shown or OTHER
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
        ({"name": k, "count": v, "pics": k in PICS_MEMBER_COUNTRIES} for k, v in country_counts.items() if k != OTHER),
        key=lambda x: (-x["count"], x["name"]),
    )[:limit]
    if country_counts.get(OTHER):
        by_country.append({"name": OTHER, "count": country_counts[OTHER], "pics": False})

    return {
        "by_country":      by_country,
        "mismatch_count":  len(mismatches),
        "mismatches":      mismatches[:mismatch_limit],
    }


# ── 9. Month-by-month summary ─────────────────────────────────
def get_gmp_analytics_monthly(
    db: Session,
    year: str = "All",
    est_category: str = "All",
) -> list:
    """One row per month: how many records were RECEIVED that month, how many
    of those have since been released / disapproved / are still on process
    (same cohort view as the trend chart, so the numbers reconcile with the
    KPI tiles), plus `released_in_month` — records whose Released Date falls
    in that month regardless of when they were received, i.e. actual output.
    year="All" lists every month across all years."""
    rec_year = func.year(GMPRecord.GMP_DATE_RECEIVED)
    rec_month = func.month(GMPRecord.GMP_DATE_RECEIVED)
    tat_days = _wd_diff(GMPRecord.GMP_DATE_RECEIVED, GMPRecord.GMP_RELEASED_DATE)
    has_tat = GMPRecord.GMP_DATE_RECEIVED.isnot(None) & GMPRecord.GMP_RELEASED_DATE.isnot(None)

    cohort = (
        _base_query(db, year, "All", est_category)
        .filter(GMPRecord.GMP_DATE_RECEIVED.isnot(None))
        .with_entities(
            rec_year.label("yr"),
            rec_month.label("mo"),
            func.count(GMPRecord.GMP_ID).label("received"),
            _released_case().label("released"),
            _disapproved_case().label("disapproved"),
            _on_process_case().label("on_process"),
            func.avg(case((has_tat, tat_days))).cast(Float).label("avg_tat"),
        )
        .group_by("yr", "mo")
        .all()
    )

    rel_year = func.year(GMPRecord.GMP_RELEASED_DATE)
    rel_month = func.month(GMPRecord.GMP_RELEASED_DATE)
    out_q = (
        db.query(rel_year.label("yr"), rel_month.label("mo"), func.count(GMPRecord.GMP_ID).label("n"))
        .filter(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_RELEASED_DATE.isnot(None))
    )
    if est_category != "All":
        out_q = out_q.filter(GMPRecord.GMP_EST_CATEGORY == est_category)
    if year != "All":
        out_q = out_q.filter(rel_year == int(year))
    output_by_month = {(int(r.yr), int(r.mo)): int(r.n or 0) for r in out_q.group_by("yr", "mo").all()}

    merged = {}
    for r in cohort:
        if r.yr is None or r.mo is None:
            continue
        merged[(int(r.yr), int(r.mo))] = {
            "received":     int(r.received or 0),
            "released":     int(r.released or 0),
            "disapproved":  int(r.disapproved or 0),
            "on_process":   int(r.on_process or 0),
            "avg_tat_days": round(r.avg_tat, 1) if r.avg_tat is not None else None,
        }
    for key in output_by_month:
        merged.setdefault(key, {"received": 0, "released": 0, "disapproved": 0, "on_process": 0, "avg_tat_days": None})

    result = []
    for (yr, mo) in sorted(merged):
        m = merged[(yr, mo)]
        result.append({
            "period":            f"{yr}-{mo:02d}",
            "label":             f"{MONTH_ABBR.get(mo, mo)} {yr}",
            "received":          m["received"],
            "released":          m["released"],
            "disapproved":       m["disapproved"],
            "on_process":        m["on_process"],
            "release_rate":      round(m["released"] / m["received"] * 100, 1) if m["received"] else 0.0,
            "released_in_month": output_by_month.get((yr, mo), 0),
            "avg_tat_days":      m["avg_tat_days"],
        })
    return result


# ── 9b. Mini trends for the KPI tiles ─────────────────────────
def get_gmp_analytics_sparklines(
    db: Session,
    year: str = "All",
    month: str = "All",
    est_category: str = "All",
) -> dict:
    """The series behind the little trend line on each KPI tile: one point per
    DAY. Same cohort view as the monthly table — each point is the records
    RECEIVED that day, split by where they stand now. Days with nothing
    received count as 0, so the line follows the real rhythm of the work.
      - a month picked: that whole month
      - otherwise: from the first to the last day that has records, in the
        picked year (or across all years)
    """
    day = GMPRecord.GMP_DATE_RECEIVED
    tat_days = _wd_diff(GMPRecord.GMP_DATE_RECEIVED, GMPRecord.GMP_RELEASED_DATE)
    has_tat = GMPRecord.GMP_DATE_RECEIVED.isnot(None) & GMPRecord.GMP_RELEASED_DATE.isnot(None)
    rows = (
        _base_query(db, year, month, est_category)
        .filter(GMPRecord.GMP_DATE_RECEIVED.isnot(None))
        .with_entities(
            day.label("d"),
            func.count(GMPRecord.GMP_ID).label("received"),
            _released_case().label("released"),
            _disapproved_case().label("disapproved"),
            _on_process_case().label("on_process"),
            func.avg(case((has_tat, tat_days))).cast(Float).label("avg_tat"),
        )
        .group_by("d")
        .all()
    )
    by_day = {r.d: r for r in rows if r.d is not None}
    if not by_day:
        return {"granularity": "day", "points": []}
    if year != "All" and month != "All":
        start = date(int(year), int(month), 1)
        end = date(int(year), int(month), calendar.monthrange(int(year), int(month))[1])
    else:
        start, end = min(by_day), max(by_day)

    points = []
    for offset in range((end - start).days + 1):
        d = start + timedelta(days=offset)
        r = by_day.get(d)
        points.append({
            "date":         d.isoformat(),
            "label":        f"{MONTH_ABBR[d.month]} {d.day}, {d.year}" if year == "All" else f"{MONTH_ABBR[d.month]} {d.day}",
            "received":     int(r.received or 0) if r else 0,
            "released":     int(r.released or 0) if r else 0,
            "disapproved":  int(r.disapproved or 0) if r else 0,
            "on_process":   int(r.on_process or 0) if r else 0,
            "avg_tat_days": round(r.avg_tat, 1) if r and r.avg_tat is not None else None,
        })
    return {"granularity": "day", "points": points}


# ── 10. Data completeness (Date Received / Released Date / Type of Issuance) ──
# Mirrors CPR's Data Completeness (crud/analytics.py) so both read the same:
#   Date Received    — always expected
#   Released Date    — expected once the record is RELEASED / COMPLETED
#   Type of Issuance — expected once RELEASED / COMPLETED, or a release date exists
# FGMP stores real DATE columns, so "valid" only means present and in a sane
# 2000–2100 range (no text like "NOD 90" to catch, unlike CPR).
def _quality_exprs():
    def valid(col):
        return and_(col.isnot(None), func.year(col) >= 2000, func.year(col) <= 2100)

    rec_ok = valid(GMPRecord.GMP_DATE_RECEIVED)
    rel_ok = valid(GMPRecord.GMP_RELEASED_DATE)
    status = func.upper(func.trim(func.coalesce(GMPRecord.GMP_APP_STATUS, "")))
    expects = status.in_(["RELEASED", "COMPLETED"])
    doc_ok = func.trim(func.coalesce(GMPRecord.GMP_TYPE_OF_ISSUANCE, "")) != ""
    expects_doc = or_(expects, rel_ok)
    complete = and_(rec_ok, or_(~expects, rel_ok), or_(~expects_doc, doc_ok))
    ref_year = case(
        (rec_ok, func.year(GMPRecord.GMP_DATE_RECEIVED)),
        (rel_ok, func.year(GMPRecord.GMP_RELEASED_DATE)),
        else_=None,
    )
    return rec_ok, rel_ok, doc_ok, expects, expects_doc, complete, ref_year


def get_gmp_analytics_data_quality(db: Session, est_category: str = "All") -> list:
    rec_ok, rel_ok, doc_ok, expects, expects_doc, complete, ref_year = _quality_exprs()

    q = db.query(
        ref_year.label("yr"),
        func.count(GMPRecord.GMP_ID).label("total"),
        func.sum(case((rec_ok, 1), else_=0)).label("n_rec"),
        func.sum(case((expects, 1), else_=0)).label("n_exp"),
        func.sum(case((and_(expects, rel_ok), 1), else_=0)).label("n_rel"),
        func.sum(case((expects_doc, 1), else_=0)).label("n_expdoc"),
        func.sum(case((and_(expects_doc, doc_ok), 1), else_=0)).label("n_doc"),
        func.sum(case((complete, 1), else_=0)).label("n_done"),
    ).filter(GMPRecord.GMP_TRASH.is_(None))
    if est_category != "All":
        q = q.filter(GMPRecord.GMP_EST_CATEGORY == est_category)

    out = []
    for r in q.group_by("yr").all():
        total, n_rec, n_exp = int(r.total or 0), int(r.n_rec or 0), int(r.n_exp or 0)
        n_rel, n_expdoc, n_doc, n_done = int(r.n_rel or 0), int(r.n_expdoc or 0), int(r.n_doc or 0), int(r.n_done or 0)
        out.append({
            "year":             str(r.yr) if r.yr is not None else "No Date",
            "total":            total,
            "received_filled":  n_rec,
            "missing_received": total - n_rec,
            "release_expected": n_exp,
            "released_filled":  n_rel,
            "missing_released": n_exp - n_rel,
            "doc_expected":     n_expdoc,
            "doc_filled":       n_doc,
            "missing_doc":      n_expdoc - n_doc,
            "complete":         n_done,
            "incomplete":       total - n_done,
            "completeness":     round(n_done / total * 100, 1) if total else 0.0,
        })
    out.sort(key=lambda x: (x["year"] == "No Date", int(x["year"]) if x["year"] != "No Date" else 0))
    return out


def get_gmp_analytics_quality_records(
    db: Session,
    year: str = "all",
    issue: str = "incomplete",
    page: int = 1,
    page_size: int = 50,
    search: str = None,
) -> dict:
    """Records behind one Data Completeness cell. issue: incomplete |
    missing_received | missing_released | missing_doc. year: "all", a year, or
    "No Date"."""
    rec_ok, rel_ok, doc_ok, expects, expects_doc, complete, ref_year = _quality_exprs()
    q = db.query(GMPRecord).filter(GMPRecord.GMP_TRASH.is_(None))

    if year == "No Date":
        q = q.filter(ref_year.is_(None))
    elif year != "all":
        q = q.filter(ref_year == int(year))

    if issue == "missing_received":
        q = q.filter(~rec_ok)
    elif issue == "missing_released":
        q = q.filter(expects, ~rel_ok)
    elif issue == "missing_doc":
        q = q.filter(expects_doc, ~doc_ok)
    else:
        q = q.filter(~complete)

    if search:
        s = f"%{search.strip()}%"
        q = q.filter(or_(
            cast(GMPRecord.GMP_DTN, String).like(s),
            GMPRecord.GMP_LTO_COMPANY.like(s),
        ))

    page = max(1, page)
    page_size = max(1, min(200, page_size))
    total = q.count()
    rows = (
        q.order_by(GMPRecord.GMP_ID.desc())
        .offset((page - 1) * page_size).limit(page_size).all()
    )

    def _missing(r):
        status = (r.GMP_APP_STATUS or "").strip().upper()
        released_like = status in ("RELEASED", "COMPLETED")
        has_rel = r.GMP_RELEASED_DATE is not None
        miss = []
        if r.GMP_DATE_RECEIVED is None:
            miss.append("Date Received")
        if released_like and not has_rel:
            miss.append("Released Date")
        if (released_like or has_rel) and not (r.GMP_TYPE_OF_ISSUANCE or "").strip():
            miss.append("Type of Issuance")
        return miss

    return {
        "data": [{
            "gmp_id":           r.GMP_ID,
            "dtn":              str(r.GMP_DTN) if r.GMP_DTN is not None else None,
            "reference_no":     r.GMP_REFERENCE_NO,
            "company":          r.GMP_LTO_COMPANY,
            "status":           r.GMP_APP_STATUS,
            "current_step":     r.GMP_CURRENT_STEP,
            "date_received":    str(r.GMP_DATE_RECEIVED) if r.GMP_DATE_RECEIVED is not None else None,
            "released_date":    str(r.GMP_RELEASED_DATE) if r.GMP_RELEASED_DATE is not None else None,
            "type_of_issuance": r.GMP_TYPE_OF_ISSUANCE,
            "missing":          _missing(r),
        } for r in rows],
        "total":       total,
        "page":        page,
        "total_pages": max(1, -(-total // page_size)),
    }
