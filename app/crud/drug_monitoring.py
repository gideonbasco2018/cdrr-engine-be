# app/crud/drug_monitoring.py
"""Drill-down data for one drug (brand name) from the Top Drug Applications list."""

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.main_db import MainDB
from app.crud.analytics import (
    _base_query,
    _completed_case,
    _cpr_case,
    _date_range_conds,
    _doc_key_expr,
    _in_progress_case,
    _is_completed,
    _lod_case,
    _on_process_case,
    _status_key_expr,
    _valid_date_cond,
)


def _drug_scope(db: Session, name: str, year, month, prescription):
    """All applications of one brand name, using the same filters as the list."""
    return _base_query(db, year, month, prescription).filter(
        MainDB.DB_PROD_BR_NAME == name
    )


def _facet(rows) -> list:
    return sorted(
        [{"key": r.k, "count": int(r.n or 0)} for r in rows if r.k is not None],
        key=lambda x: (-x["count"], str(x["key"])),
    )


def get_drug_detail(
    db: Session,
    name: str,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> dict:
    def scope():
        return _drug_scope(db, name, year, month, prescription)

    rec = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rel = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")

    # ── Totals ────────────────────────────────────────────────
    agg = (
        scope()
        .with_entities(
            func.count(MainDB.DB_ID).label("total"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _completed_case().label("completed"),
            _in_progress_case().label("in_progress"),
            _on_process_case().label("on_process"),
            func.min(rec).label("first_received"),
            func.max(rec).label("last_received"),
        )
        .one()
    )

    total = int(agg.total or 0)
    cpr = int(agg.cpr or 0)
    summary = {
        "total": total,
        "cpr": cpr,
        "lod": int(agg.lod or 0),
        "completed": int(agg.completed or 0),
        "in_progress": int(agg.in_progress or 0),
        "on_process": int(agg.on_process or 0),
        "rate": round(cpr / total * 100, 1) if total else 0.0,
        "first_received": str(agg.first_received) if agg.first_received else None,
        "last_received": str(agg.last_received) if agg.last_received else None,
    }

    # ── Received / Released per year ──────────────────────────
    # Same definitions as the Received vs Released chart:
    #   Received = valid Date Received; Released = COMPLETED with valid Date Released.
    rec_rows = (
        scope()
        .filter(_valid_date_cond(MainDB.DB_DATE_RECEIVED_CENT))
        .with_entities(func.year(rec).label("k"), func.count(MainDB.DB_ID).label("n"))
        .group_by("k")
        .all()
    )
    rel_rows = (
        scope()
        .filter(_valid_date_cond(MainDB.DB_DATE_RELEASED), _is_completed())
        .with_entities(func.year(rel).label("k"), func.count(MainDB.DB_ID).label("n"))
        .group_by("k")
        .all()
    )
    rc = {int(r.k): int(r.n or 0) for r in rec_rows if r.k is not None}
    rl = {int(r.k): int(r.n or 0) for r in rel_rows if r.k is not None}
    by_year = [
        {"year": y, "received": rc.get(y, 0), "released": rl.get(y, 0)}
        for y in sorted(set(rc) | set(rl))
    ]

    # ── Facets ────────────────────────────────────────────────
    def facet(expr, extra=None, limit=None):
        q = scope().with_entities(expr.label("k"), func.count(MainDB.DB_ID).label("n"))
        if extra is not None:
            q = q.filter(extra)
        out = _facet(q.group_by("k").all())
        return out[:limit] if limit else out

    def non_blank(col):
        return and_(col.isnot(None), func.trim(col) != "")

    countries = facet(
        MainDB.DB_PROD_MANU_COUNTRY,
        non_blank(MainDB.DB_PROD_MANU_COUNTRY),
        limit=6,
    )
    generics = facet(
        MainDB.DB_PROD_GEN_NAME, non_blank(MainDB.DB_PROD_GEN_NAME), limit=5
    )
    classes = facet(
        MainDB.DB_PROD_CLASS_PRESCRIP, non_blank(MainDB.DB_PROD_CLASS_PRESCRIP)
    )

    return {
        "name": name,
        "summary": summary,
        "by_year": by_year,
        "statuses": facet(_status_key_expr()),
        "doc_types": facet(_doc_key_expr()),
        "countries": countries,
        "generics": generics,
        "classifications": classes,
    }


def get_drug_records(
    db: Session,
    name: str,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
    page: int = 1,
    page_size: int = 50,
    search: str = None,
    status: str = None,
    doc_type: str = None,
    received_from=None,
    received_to=None,
    released_from=None,
    released_to=None,
) -> dict:
    """Same response shape as the other analytics record drill-downs."""
    doc_key = _doc_key_expr()
    status_key = _status_key_expr()
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    ranges = _date_range_conds(received_from, received_to, released_from, released_to)

    def base():
        return _drug_scope(db, name, year, month, prescription).filter(*ranges)

    def narrowed(q, use_status=True, use_doc=True):
        if search:
            q = q.filter(func.concat(MainDB.DB_DTN, "").like(f"%{search}%"))
        if use_status and status:
            q = q.filter(status_key == status)
        if use_doc and doc_type:
            q = q.filter(doc_key == doc_type)
        return q

    rows_q = narrowed(
        base().with_entities(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_DATE_RECEIVED_CENT,
            MainDB.DB_DATE_RELEASED,
            MainDB.DB_TYPE_DOC_RELEASED,
            MainDB.DB_APP_STATUS,
            MainDB.DB_ENTRY_TYPE,
            MainDB.DB_PROD_BR_NAME,
            MainDB.DB_PROD_GEN_NAME,
        )
    )
    total = rows_q.count()
    rows = (
        rows_q.order_by(rec_date.desc(), MainDB.DB_ID.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    status_rows = (
        narrowed(
            base().with_entities(
                status_key.label("k"), func.count(MainDB.DB_ID).label("n")
            ),
            use_status=False,
        )
        .group_by("k")
        .all()
    )
    doc_rows = (
        narrowed(
            base().with_entities(
                doc_key.label("k"), func.count(MainDB.DB_ID).label("n")
            ),
            use_doc=False,
        )
        .group_by("k")
        .all()
    )

    def _d(v):
        return str(v)[:10] if v else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_counts": _facet(status_rows),
        "doc_type_counts": _facet(doc_rows),
        "data": [
            {
                "db_id": r.DB_ID,
                "dtn": str(r.DB_DTN) if r.DB_DTN else None,
                "entry_type": r.DB_ENTRY_TYPE or None,
                "date_received_cent": _d(r.DB_DATE_RECEIVED_CENT),
                "date_released": _d(r.DB_DATE_RELEASED),
                "type_doc_released": r.DB_TYPE_DOC_RELEASED or None,
                "app_status": r.DB_APP_STATUS or None,
                "brand_name": r.DB_PROD_BR_NAME or None,
                "generic_name": r.DB_PROD_GEN_NAME or None,
            }
            for r in rows
        ],
    }


def get_drug_timeline(
    db: Session,
    name: str,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
    group_by: str = "year",  # year | month | day
    bucket_year: int = None,  # needed for month / day
    bucket_month: int = None,  # needed for day
    basis: str = "received",  # received | released
    search: str = None,
    status: str = None,
    doc_type: str = None,
) -> dict:
    """Records of one drug counted per year / month / day (by received or released date)."""
    import calendar

    basis = "released" if basis == "released" else "received"
    date_col = (
        MainDB.DB_DATE_RELEASED if basis == "released" else MainDB.DB_DATE_RECEIVED_CENT
    )
    t = func.str_to_date(func.left(date_col, 10), "%Y-%m-%d")
    valid = _valid_date_cond(date_col)

    doc_key = _doc_key_expr()
    status_key = _status_key_expr()

    def base():
        q = _drug_scope(db, name, year, month, prescription)
        if search:
            q = q.filter(func.concat(MainDB.DB_DTN, "").like(f"%{search}%"))
        if status:
            q = q.filter(status_key == status)
        if doc_type:
            q = q.filter(doc_key == doc_type)
        return q

    if group_by == "day" and bucket_year and bucket_month:
        mode, expr = "day", func.day(t)
    elif group_by in ("month", "day") and bucket_year:
        mode, expr = "month", func.month(t)
    else:
        mode, expr = "year", func.year(t)

    q = base().filter(valid)
    if mode in ("month", "day"):
        q = q.filter(func.year(t) == int(bucket_year))
    if mode == "day":
        q = q.filter(func.month(t) == int(bucket_month))

    rows = (
        q.with_entities(expr.label("k"), func.count(MainDB.DB_ID).label("n"))
        .group_by("k")
        .all()
    )
    counts = {int(r.k): int(r.n or 0) for r in rows if r.k is not None}

    month_abbr = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    if mode == "day":
        last = calendar.monthrange(int(bucket_year), int(bucket_month))[1]
        data = [
            {"key": d, "label": str(d), "count": counts.get(d, 0)}
            for d in range(1, last + 1)
        ]
    elif mode == "month":
        data = [
            {"key": m, "label": month_abbr[m - 1], "count": counts.get(m, 0)}
            for m in range(1, 13)
        ]
    else:
        data = [{"key": y, "label": str(y), "count": counts[y]} for y in sorted(counts)]

    no_date = int(
        base().filter(~valid).with_entities(func.count(MainDB.DB_ID)).scalar() or 0
    )

    return {
        "group_by": mode,
        "basis": basis,
        "data": data,
        "no_date": no_date,
        "total": sum(x["count"] for x in data),
    }
