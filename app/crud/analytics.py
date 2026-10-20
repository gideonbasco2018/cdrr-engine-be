# app/crud/analytics.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, case, func, Float, Integer, literal, or_
from app.models.main_db import MainDB

MONTH_ABBR = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def _base_query(db, year="All", month="All", prescription="All"):
    q = db.query(MainDB)
    if prescription != "All":
        q = q.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    if year != "All":
        q = q.filter(
            func.year(
                func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
            )
            == int(year)
        )
        if month != "All":
            q = q.filter(
                func.month(
                    func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
                )
                == int(month)
            )
    return q


def _cpr_case():
    return func.sum(case((MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%"), 1), else_=0))


def _lod_case():
    return func.sum(case((MainDB.DB_TYPE_DOC_RELEASED.ilike("%LOD%"), 1), else_=0))


def _on_process_case():
    return func.sum(
        case(
            (
                or_(
                    MainDB.DB_APP_STATUS.ilike("ON-PROCESS"),
                    MainDB.DB_APP_STATUS.ilike("ON PROCESS"),
                ),
                1,
            ),
            else_=0,
        )
    )


def _completed_case():
    return func.sum(case((MainDB.DB_APP_STATUS.ilike("COMPLETED"), 1), else_=0))


CPR_EXPIRY_FIELD = "DB_SECPA_EXP_DATE"


def _in_progress_case():
    return func.sum(
        case(
            (
                or_(
                    MainDB.DB_APP_STATUS.ilike("IN PROGRESS"),
                    MainDB.DB_APP_STATUS.ilike("IN-PROGRESS"),
                ),
                1,
            ),
            else_=0,
        )
    )


def _is_completed():
    return func.upper(func.trim(MainDB.DB_APP_STATUS)) == "COMPLETED"


def _doc_completed_case(pattern):
    """Count of rows whose doc type matches `pattern` AND status is COMPLETED."""
    return func.sum(
        case(
            (and_(MainDB.DB_TYPE_DOC_RELEASED.ilike(pattern), _is_completed()), 1),
            else_=0,
        )
    )


def _cpr_expiry_cases():
    """(expired, not_expired) counts among COMPLETED CPR rows, by expiry date vs today."""
    col = getattr(MainDB, CPR_EXPIRY_FIELD)
    exp_date = func.str_to_date(func.left(col, 10), "%Y-%m-%d")
    is_cpr = and_(MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%"), _is_completed())
    expired = func.sum(
        case(
            (and_(is_cpr, exp_date.isnot(None), exp_date < func.curdate()), 1),
            else_=0,
        )
    )
    not_expired = func.sum(
        case(
            (and_(is_cpr, exp_date.isnot(None), exp_date >= func.curdate()), 1),
            else_=0,
        )
    )
    return expired, not_expired


def _wd_diff(start_col, end_col):
    _LUT = literal("0123444401234443012345440123456601234566")
    n = func.datediff(end_col, start_col)
    w1 = func.weekday(start_col)
    w2 = func.weekday(end_col)
    return func.floor(n / 7) * 5 + func.cast(
        func.substr(_LUT, w1 * 7 + w2 + 1, 1), Integer
    )


# ── 1. Available Years ────────────────────────────────────────
def get_analytics_available_years(db: Session) -> list:
    date_col = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    year_col = func.year(date_col)
    rows = (
        db.query(year_col.label("yr"))
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_DATE_RELEASED != "N/A",
            date_col.isnot(None),
            year_col >= 2000,
            year_col <= 2100,
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
    cpr_expired_expr, cpr_not_expired_expr = _cpr_expiry_cases()
    row = (
        _base_query(db, year, month, prescription)
        .with_entities(
            func.count(MainDB.DB_ID).label("total"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _on_process_case().label("on_process"),
            _in_progress_case().label("in_progress"),
            _completed_case().label("completed"),
            _doc_completed_case("%CPR%").label("cpr_completed"),
            _doc_completed_case("%LOD%").label("lod_completed"),
            cpr_expired_expr.label("cpr_expired"),
            cpr_not_expired_expr.label("cpr_not_expired"),
        )
        .one()
    )
    total = int(row.total or 0)
    cpr = int(row.cpr or 0)
    cpr_completed = int(row.cpr_completed or 0)
    cpr_expired = int(row.cpr_expired or 0)
    cpr_not_expired = int(row.cpr_not_expired or 0)
    return {
        "total": total,
        "cpr": cpr,
        "lod": int(row.lod or 0),
        "on_process": int(row.on_process or 0),
        "in_progress": int(row.in_progress or 0),
        "completed": int(row.completed or 0),
        "cpr_expired": cpr_expired,
        "cpr_not_expired": cpr_not_expired,
        "cpr_completed": cpr_completed,
        "lod_completed": int(row.lod_completed or 0),
        # completed CPR rows with no (or unreadable) expiry date
        "cpr_no_expiry": max(cpr_completed - cpr_expired - cpr_not_expired, 0),
        "approval_rate": round(cpr / total * 100, 1) if total else 0.0,
    }


# ── 3. Trend Chart ────────────────────────────────────────────
# ── 3. Trend Chart ────────────────────────────────────────────
def get_analytics_trend(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    by_year = year == "All"

    rel_date = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")

    rel_grp = (func.year(rel_date) if by_year else func.month(rel_date)).label("grp")
    rec_grp = (func.year(rec_date) if by_year else func.month(rec_date)).label("grp")

    # CPR / LOD / Completed: bucketed by release date
    released_rows = (
        _base_query(db, year, month, prescription)
        .filter(
            MainDB.DB_DATE_RELEASED.isnot(None),
            MainDB.DB_DATE_RELEASED != "",
            MainDB.DB_DATE_RELEASED != "N/A",
            rel_date.isnot(None),
            func.year(rel_date) >= 2000,
            func.year(rel_date) <= 2100,
        )
        .with_entities(
            rel_grp,
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _completed_case().label("completed"),
        )
        .group_by("grp")
        .all()
    )

    # In Progress: not released yet, so bucketed by received date
    ip_q = db.query(
        rec_grp,
        _in_progress_case().label("in_progress"),
    ).filter(
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        rec_date.isnot(None),
        func.year(rec_date) >= 2000,
        func.year(rec_date) <= 2100,
    )
    if prescription != "All":
        ip_q = ip_q.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    if not by_year:
        ip_q = ip_q.filter(func.year(rec_date) == int(year))
        if month != "All":
            ip_q = ip_q.filter(func.month(rec_date) == int(month))
    ip_rows = ip_q.group_by("grp").all()

    # Merge both result sets by bucket
    buckets = {}
    for r in released_rows:
        if r.grp is None:
            continue
        buckets[int(r.grp)] = {
            "cpr": int(r.cpr or 0),
            "lod": int(r.lod or 0),
            "completed": int(r.completed or 0),
            "in_progress": 0,
        }
    for r in ip_rows:
        if r.grp is None:
            continue
        b = buckets.setdefault(
            int(r.grp), {"cpr": 0, "lod": 0, "completed": 0, "in_progress": 0}
        )
        b["in_progress"] = int(r.in_progress or 0)

    result = []
    for key in sorted(buckets):
        label = str(key) if by_year else MONTH_ABBR.get(key, str(key))
        result.append({"label": label, **buckets[key]})
    return result


# ── 4. By Classification ──────────────────────────────────────
def get_analytics_by_classification(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
) -> list:
    # Step 1: get all distinct doc types dynamically
    doc_types = (
        db.query(MainDB.DB_TYPE_DOC_RELEASED)
        .filter(
            MainDB.DB_TYPE_DOC_RELEASED.isnot(None),
            MainDB.DB_TYPE_DOC_RELEASED != "",
        )
        .distinct()
        .all()
    )
    doc_types = [r[0] for r in doc_types if r[0]]

    # Step 2: build dynamic SUM(CASE WHEN ...) per doc type
    dynamic_cols = [
        func.sum(case((MainDB.DB_TYPE_DOC_RELEASED == dt, 1), else_=0)).label(dt)
        for dt in doc_types
    ]

    # Step 3: run the main query
    rows = (
        _base_query(db, year, month, prescription)
        .filter(
            MainDB.DB_PROD_CLASS_PRESCRIP.isnot(None),
            MainDB.DB_PROD_CLASS_PRESCRIP != "",
        )
        .with_entities(
            MainDB.DB_PROD_CLASS_PRESCRIP.label("type"),
            func.count(MainDB.DB_ID).label("count"),
            *dynamic_cols,
        )
        .group_by(MainDB.DB_PROD_CLASS_PRESCRIP)
        .order_by(func.count(MainDB.DB_ID).desc())
        .all()
    )

    result = []
    for r in rows:
        entry = {
            "type": r.type,
            "count": int(r.count or 0),
            "by_doc_type": {dt: int(getattr(r, dt) or 0) for dt in doc_types},
        }
        result.append(entry)

    return result, doc_types


# ── 5. Year-by-Year Summary ───────────────────────────────────
def get_analytics_year_summary(db: Session, basis: str = "released") -> list:
    """
    basis="released" (default): Released is counted by the year it was released.
    basis="received": Released is counted by the year it was RECEIVED, i.e.
                      out of the applications received in year X, how many
                      have been released (regardless of release year).
    """
    basis = "received" if basis == "received" else "released"

    rel_date = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    rel_year = func.year(rel_date)
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rec_year = func.year(rec_date)

    # Released side: which year do released records get grouped under?
    group_year = rec_year if basis == "received" else rel_year

    released_filters = [
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        rel_date.isnot(None),
        rel_year >= 2000,
        rel_year <= 2100,
    ]
    if basis == "received":
        # must also have a valid received date to be grouped by it
        released_filters += [
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
            rec_date.isnot(None),
            rec_year >= 2000,
            rec_year <= 2100,
        ]

    released_rows = (
        db.query(
            group_year.label("yr"),
            func.count(MainDB.DB_ID).label("total"),
            _cpr_case().label("cpr"),
            _lod_case().label("lod"),
            _on_process_case().label("on_process"),
            _completed_case().label("completed"),
        )
        .filter(*released_filters)
        .group_by("yr")
        .all()
    )

    # Received side: grouped by the year received by the center
    received_rows = (
        db.query(
            rec_year.label("yr"),
            func.count(MainDB.DB_ID).label("received"),
        )
        .filter(
            MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
            MainDB.DB_DATE_RECEIVED_CENT != "",
            MainDB.DB_DATE_RECEIVED_CENT != "N/A",
            rec_date.isnot(None),
            rec_year >= 2000,
            rec_year <= 2100,
        )
        .group_by("yr")
        .all()
    )

    released_map = {str(r.yr): r for r in released_rows}
    received_map = {str(r.yr): int(r.received or 0) for r in received_rows}

    result = []
    for yr in sorted(set(released_map) | set(received_map)):
        r = released_map.get(yr)
        total = int(r.total or 0) if r else 0
        cpr = int(r.cpr or 0) if r else 0
        result.append(
            {
                "year": yr,
                "received": received_map.get(yr, 0),
                "total": total,  # total released
                "cpr": cpr,
                "lod": int(r.lod or 0) if r else 0,
                "on_process": int(r.on_process or 0) if r else 0,
                "completed": int(r.completed or 0) if r else 0,
                "rate": round(cpr / total * 100, 1) if total else 0.0,
            }
        )
    return result


def _doc_key_expr():
    """Normalized doc-type key. Cert/Certificate -> CERT, blank -> __NONE__."""
    trimmed = func.trim(MainDB.DB_TYPE_DOC_RELEASED)
    return case(
        (MainDB.DB_TYPE_DOC_RELEASED.is_(None), "__NONE__"),
        (trimmed == "", "__NONE__"),
        (func.lower(trimmed).in_(["cert", "certificate"]), "CERT"),
        else_=trimmed,
    )


def _status_key_expr():
    """Normalized app-status key. Upper-cased, blank -> __NONE__."""
    upper = func.upper(func.trim(MainDB.DB_APP_STATUS))
    return case(
        (MainDB.DB_APP_STATUS.is_(None), "__NONE__"),
        (upper == "", "__NONE__"),
        else_=upper,
    )


# ── 5b. Year-by-Year Summary — record drill-down ──────────────
def get_analytics_year_records(
    db: Session,
    year: int,
    kind: str = "released",
    basis: str = "released",
    page: int = 1,
    page_size: int = 50,
    search: str = None,
    status: str = None,
    doc_type: str = None,
) -> dict:
    """
    List the records behind a Year-by-Year Summary cell.

    kind="received": applications received in `year`.
    kind="released":
        basis="released" -> released in `year`
        basis="received" -> received in `year` AND already released

    Optional filters: search (DTN), status (normalized DB_APP_STATUS key),
    doc_type (normalized DB_TYPE_DOC_RELEASED key).

    Also returns status_counts / doc_type_counts over the WHOLE filtered
    set (not just the current page). Each facet ignores its own filter so
    the other options stay selectable.
    """
    kind = "received" if kind == "received" else "released"
    basis = "received" if basis == "received" else "released"

    rel_date = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    rel_year = func.year(rel_date)
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rec_year = func.year(rec_date)

    rel_valid = [
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        rel_date.isnot(None),
        rel_year >= 2000,
        rel_year <= 2100,
    ]
    rec_valid = [
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        rec_date.isnot(None),
        rec_year >= 2000,
        rec_year <= 2100,
    ]

    # Which records belong to the clicked cell (same rules as year-summary)
    if kind == "received":
        scope = [*rec_valid, rec_year == year]
        order_date = rec_date
    elif basis == "received":
        scope = [*rel_valid, *rec_valid, rec_year == year]
        order_date = rec_date
    else:
        scope = [*rel_valid, rel_year == year]
        order_date = rel_date

    doc_key = _doc_key_expr()
    status_key = _status_key_expr()

    def narrowed(q, use_status=True, use_doc=True):
        if search:
            q = q.filter(func.concat(MainDB.DB_DTN, "").like(f"%{search}%"))
        if use_status and status:
            q = q.filter(status_key == status)
        if use_doc and doc_type:
            q = q.filter(doc_key == doc_type)
        return q

    # ── Rows (paged) ──
    rows_q = narrowed(
        db.query(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_DATE_RECEIVED_CENT,
            MainDB.DB_DATE_RELEASED,
            MainDB.DB_TYPE_DOC_RELEASED,
            MainDB.DB_APP_STATUS,
            MainDB.DB_ENTRY_TYPE,
            MainDB.DB_PROD_BR_NAME,
            MainDB.DB_PROD_GEN_NAME,
        ).filter(*scope)
    )
    total = rows_q.count()
    rows = (
        rows_q.order_by(order_date.asc(), MainDB.DB_ID.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # ── Facet: status counts (ignores status filter) ──
    status_rows = (
        narrowed(
            db.query(status_key.label("k"), func.count(MainDB.DB_ID).label("n")).filter(
                *scope
            ),
            use_status=False,
        )
        .group_by("k")
        .all()
    )
    status_counts = sorted(
        [{"key": r.k, "count": int(r.n or 0)} for r in status_rows],
        key=lambda x: (-x["count"], x["key"]),
    )

    # ── Facet: doc type counts (ignores doc type filter) ──
    doc_rows = (
        narrowed(
            db.query(doc_key.label("k"), func.count(MainDB.DB_ID).label("n")).filter(
                *scope
            ),
            use_doc=False,
        )
        .group_by("k")
        .all()
    )
    doc_type_counts = sorted(
        [{"key": r.k, "count": int(r.n or 0)} for r in doc_rows],
        key=lambda x: (-x["count"], x["key"]),
    )

    def _d(v):
        return str(v)[:10] if v else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_counts": status_counts,
        "doc_type_counts": doc_type_counts,
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


# ── 2b. Summary KPI — record drill-down (CPR / LOD) ───────────
def get_analytics_summary_records(
    db: Session,
    year: str = "All",
    month: str = "All",
    prescription: str = "All",
    doc: str = "cpr",
    expiry: str = "all",
    page: int = 1,
    page_size: int = 50,
    search: str = None,
    status: str = None,
    doc_type: str = None,
    completed_only: bool = False,
) -> dict:
    """
    Records behind the CPR / LOD figures in the summary KPI hover.

    doc="cpr" | "lod"
    expiry (CPR only): "all" | "expired" | "not_expired" | "none"
    Uses the same base filters (year/month/prescription) and the same
    CPR/LOD matching as get_analytics_summary, so counts line up.
    """
    doc = "lod" if doc == "lod" else "cpr"
    pattern = "%LOD%" if doc == "lod" else "%CPR%"

    exp_col = getattr(MainDB, CPR_EXPIRY_FIELD)
    exp_date = func.str_to_date(func.left(exp_col, 10), "%Y-%m-%d")
    rel_date = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")

    scope = [MainDB.DB_TYPE_DOC_RELEASED.ilike(pattern)]
    if completed_only:
        scope.append(_is_completed())
    if doc == "cpr":
        if expiry == "expired":
            scope += [exp_date.isnot(None), exp_date < func.curdate()]
        elif expiry == "not_expired":
            scope += [exp_date.isnot(None), exp_date >= func.curdate()]
        elif expiry == "none":
            scope.append(exp_date.is_(None))

    doc_key = _doc_key_expr()
    status_key = _status_key_expr()

    def narrowed(q, use_status=True, use_doc=True):
        if search:
            q = q.filter(func.concat(MainDB.DB_DTN, "").like(f"%{search}%"))
        if use_status and status:
            q = q.filter(status_key == status)
        if use_doc and doc_type:
            q = q.filter(doc_key == doc_type)
        return q

    def base():
        return _base_query(db, year, month, prescription)

    # ── Rows (paged) ──
    rows_q = narrowed(
        base()
        .with_entities(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_DATE_RECEIVED_CENT,
            MainDB.DB_DATE_RELEASED,
            MainDB.DB_TYPE_DOC_RELEASED,
            MainDB.DB_APP_STATUS,
            MainDB.DB_ENTRY_TYPE,
            MainDB.DB_PROD_BR_NAME,
            MainDB.DB_PROD_GEN_NAME,
            exp_col.label("secpa_exp"),
        )
        .filter(*scope)
    )
    total = rows_q.count()
    rows = (
        rows_q.order_by(rel_date.asc(), MainDB.DB_ID.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # ── Facet: status counts (ignores status filter) ──
    status_rows = (
        narrowed(
            base()
            .with_entities(status_key.label("k"), func.count(MainDB.DB_ID).label("n"))
            .filter(*scope),
            use_status=False,
        )
        .group_by("k")
        .all()
    )
    status_counts = sorted(
        [{"key": r.k, "count": int(r.n or 0)} for r in status_rows],
        key=lambda x: (-x["count"], x["key"]),
    )

    # ── Facet: doc type counts (ignores doc type filter) ──
    doc_rows = (
        narrowed(
            base()
            .with_entities(doc_key.label("k"), func.count(MainDB.DB_ID).label("n"))
            .filter(*scope),
            use_doc=False,
        )
        .group_by("k")
        .all()
    )
    doc_type_counts = sorted(
        [{"key": r.k, "count": int(r.n or 0)} for r in doc_rows],
        key=lambda x: (-x["count"], x["key"]),
    )

    def _d(v):
        return str(v)[:10] if v else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "status_counts": status_counts,
        "doc_type_counts": doc_type_counts,
        "data": [
            {
                "db_id": r.DB_ID,
                "dtn": str(r.DB_DTN) if r.DB_DTN else None,
                "entry_type": r.DB_ENTRY_TYPE or None,
                "date_received_cent": _d(r.DB_DATE_RECEIVED_CENT),
                "date_released": _d(r.DB_DATE_RELEASED),
                "secpa_exp_date": _d(r.secpa_exp),
                "type_doc_released": r.DB_TYPE_DOC_RELEASED or None,
                "app_status": r.DB_APP_STATUS or None,
                "brand_name": r.DB_PROD_BR_NAME or None,
                "generic_name": r.DB_PROD_GEN_NAME or None,
            }
            for r in rows
        ],
    }


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
        # no .limit() — all results returned, frontend paginates
        .all()
    )
    result = []
    for r in rows:
        total = int(r.total or 0)
        cpr = int(r.cpr or 0)
        result.append(
            {
                "name": r.name,
                "generic": r.generic or "",
                "rx": r.rx or "",
                "total": total,
                "cpr": cpr,
                "lod": int(r.lod or 0),
                "rate": round(cpr / total * 100, 1) if total else 0.0,
            }
        )
    return result


# ── 7. Top Countries ─────────────────────────────────────────
ENTITY_FIELD_MAP = {
    "mfr": "DB_PROD_MANU_COUNTRY",
    "trader": "DB_PROD_TRADER_COUNTRY",
    "importer": "DB_PROD_IMPORTER_COUNTRY",
    "distributor": "DB_PROD_DISTRI_COUNTRY",
    "repacker": "DB_PROD_REPACKER_COUNTRY",
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
        # no .limit() — all results returned, frontend paginates
        .all()
    )
    return [
        {
            "country": r.country,
            "count": int(r.count or 0),
            "cpr": int(r.cpr or 0),
            "lod": int(r.lod or 0),
            "on_process": int(r.on_process or 0),
        }
        for r in rows
    ]


# ── 7b. Country Year Trend ────────────────────────────────────
def get_country_year_trend(
    db: Session,
    country: str,
    entity_type: str = "mfr",
    prescription: str = "All",
) -> list:
    field_name = ENTITY_FIELD_MAP.get(entity_type, "DB_PROD_MANU_COUNTRY")
    field = getattr(MainDB, field_name)

    date_col = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    year_col = func.year(date_col)

    rows = db.query(
        year_col.label("yr"),
        func.count(MainDB.DB_ID).label("count"),
        _cpr_case().label("cpr"),
        _lod_case().label("lod"),
        _on_process_case().label("on_process"),
    ).filter(
        field == country,
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        date_col.isnot(None),
        year_col >= 2000,
        year_col <= 2100,
    )

    if prescription != "All":
        rows = rows.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)

    rows = rows.group_by("yr").order_by("yr").all()

    return [
        {
            "year": str(r.yr),
            "count": int(r.count or 0),
            "cpr": int(r.cpr or 0),
            "lod": int(r.lod or 0),
            "on_process": int(r.on_process or 0),
        }
        for r in rows
        if r.yr
    ]


# ── 8. FRP TAT Trend ─────────────────────────────────────────
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
    year_col_received = func.year(clean_received)
    month_col_released = func.month(clean_released)
    year_col_released = func.year(clean_released)

    tat_days = _wd_diff(clean_received, clean_released)
    query = db.query(
        year_col_received.label("year_received"),
        month_col_received.label("month_num_received"),
        year_col_released.label("year_released"),
        month_col_released.label("month_num_released"),
        MainDB.DB_TIMELINE_CITIZEN_CHARTER.label("timeline_days"),
        MainDB.DB_TYPE_DOC_RELEASED.label("type_of_doc_released"),
        func.count(MainDB.DB_ID).label("total_applications"),
        func.avg(tat_days).cast(Float).label("avg_tat_days"),
        func.min(tat_days).cast(Integer).label("min_tat_days"),
        func.max(tat_days).cast(Integer).label("max_tat_days"),
    ).filter(
        MainDB.DB_PROCESSING_TYPE == "FRP and CRP",
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        MainDB.DB_TRASH.is_(None),
        func.upper(MainDB.DB_APP_STATUS) == "COMPLETED",
        clean_received.isnot(None),
        clean_released.isnot(None),
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
        query.group_by(
            "year_received",
            "month_num_received",
            "year_released",
            "month_num_released",
            "timeline_days",
            "type_of_doc_released",
        )
        .order_by("timeline_days", "year_received", "month_num_received")
        .all()
    )

    return [
        {
            "month": f"{MONTH_ABBR.get(row.month_num_received, str(row.month_num_received))} {row.year_received}",
            "year": row.year_received,
            "month_num": row.month_num_received,
            "month_released": f"{MONTH_ABBR.get(row.month_num_released, str(row.month_num_released))} {row.year_released}",
            "year_released": row.year_released,
            "month_num_released": row.month_num_released,
            "timeline_days": row.timeline_days,
            "type_of_doc_released": row.type_of_doc_released,
            "total_applications": row.total_applications,
            "avg_tat_days": (
                round(row.avg_tat_days, 2) if row.avg_tat_days is not None else None
            ),
            "min_tat_days": row.min_tat_days,
            "max_tat_days": row.max_tat_days,
        }
        for row in rows
        if row.year_received
        and row.month_num_received
        and row.year_released
        and row.month_num_released
    ]


# ── 9. FRP & CRP — TAT Outliers ──────────────────────────────
def get_analytics_frp_tat_outliers(
    db: Session,
    extreme_threshold: int = 365,
) -> dict:
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
        .order_by(tat_days)
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
                if m in [7, 8, 9]:
                    quarter = f"Sep {y}"
                elif m in [10, 11, 12]:
                    quarter = f"Dec {y}"
                elif m in [1, 2, 3]:
                    quarter = f"Mar {y}"
                else:
                    quarter = f"Jun {y}"
            except Exception:
                pass

        issue = "negative_tat" if (row.tat_days or 0) < 0 else "extreme_tat"

        result.append(
            {
                "db_id": row.DB_ID,
                "dtn": str(row.DB_DTN) if row.DB_DTN else None,
                "quarter": quarter,
                "date_received_cent": (
                    str(row.DB_DATE_RECEIVED_CENT)
                    if row.DB_DATE_RECEIVED_CENT
                    else None
                ),
                "date_released": (
                    str(row.DB_DATE_RELEASED) if row.DB_DATE_RELEASED else None
                ),
                "tat_days": row.tat_days,
                "est_company": row.DB_EST_LTO_COMP,
                "issue": issue,
            }
        )

    return {
        "total": len(result),
        "negative": sum(1 for r in result if r["issue"] == "negative_tat"),
        "extreme": sum(1 for r in result if r["issue"] == "extreme_tat"),
        "data": result,
    }
