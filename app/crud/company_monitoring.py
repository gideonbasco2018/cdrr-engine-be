# app/crud/company_monitoring.py
#
# Company Monitoring: for one or more companies, how many applications were
# received and processed per month, the turnaround time (TAT) of each
# application, and who the evaluator was.
#
# Reuses the rules already used by the other analytics views:
#   - company key      : UPPER(TRIM(DB_EST_LTO_COMP))          (Top Applicants)
#   - evaluator        : latest "Quality Evaluation" log row   (Top Applicants)
#   - working days     : Mon-Fri between two dates             (Fastest Processing)
#   - processed        : COMPLETED with a valid Date Released  (Year-by-Year)
from sqlalchemy import and_, case, func, not_, or_
from sqlalchemy.orm import Session

from app.models.main_db import MainDB
from app.models.user import User
from app.crud.fastest_processing import _workdays
from app.crud.top_companies import _evaluator_subquery

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

FORMULA = {
    "tat": "TAT = working days (Monday to Friday) from Date Received to Date Released",
    "counting": (
        "The day of receipt is not counted: received Monday and released "
        "Friday = 4 working days; same day = 0. Saturdays and Sundays are "
        "skipped. Holidays are not deducted."
    ),
    "ongoing": (
        "Applications that are not released yet are counted up to today and "
        "marked Ongoing."
    ),
    "charter": (
        "Within = TAT <= Citizen's Charter timeline of the application; "
        "Beyond = TAT > timeline."
    ),
    "processed": "Processed = COMPLETED applications with a valid Date Released.",
    "evaluator": (
        "Evaluator = the user of the latest Quality Evaluation step that was "
        "not reassigned."
    ),
}


# ── Shared expressions ───────────────────────────────────────
def _dates():
    rec = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rel = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    return rec, rel


def _valid(col, d):
    """True when `col` holds a readable date between 2000 and 2100."""
    return and_(
        col.isnot(None),
        col != "",
        col != "N/A",
        d.isnot(None),
        func.year(d) >= 2000,
        func.year(d) <= 2100,
    )


def _completed():
    status = func.upper(func.trim(func.coalesce(MainDB.DB_APP_STATUS, "")))
    return status == "COMPLETED"


def _period(d, year, month):
    """Year / month filter on date expression `d` (month only with a year)."""
    conds = []
    if year not in (None, "", "All"):
        conds.append(func.year(d) == int(year))
        if month not in (None, "", "All"):
            conds.append(func.month(d) == int(month))
    return conds


def _ckey():
    return func.upper(func.trim(MainDB.DB_EST_LTO_COMP))


def _norm(company: str) -> str:
    return (company or "").strip().upper()


def _norms(companies) -> list:
    """Normalized, de-duplicated company keys (accepts a string or a list)."""
    if isinstance(companies, str):
        companies = [companies]
    seen, out = set(), []
    for c in companies or []:
        k = _norm(c)
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _in_companies(companies):
    """True when the row belongs to any of the selected companies."""
    return _ckey().in_(_norms(companies))


def _r1(v):
    return round(float(v), 1) if v is not None else None


def _full_name(u) -> str:
    return f"{(u.first_name or '').strip()} {(u.surname or '').strip()}".strip()


def _evaluator(user_id, uname, names) -> dict:
    if user_id is None:
        return {
            "user_id": None,
            "code": "Unassigned",
            "full_name": "",
            "unassigned": True,
        }
    return {
        "user_id": user_id,
        "code": (uname or "").strip() or f"User #{user_id}",
        "full_name": names.get(user_id, ""),
        "unassigned": False,
    }


def _names(db: Session, user_ids) -> dict:
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    return {u.id: _full_name(u) for u in db.query(User).filter(User.id.in_(ids)).all()}


def _scope(basis, year, month, companies):
    """Filters for the applications of the selected companies in the period.

    basis = "received": received in the period.
    basis = "released": processed (completed + released) in the period.
    """
    rec, rel = _dates()
    base = [_in_companies(companies)]
    if basis == "released":
        return base + [
            _completed(),
            _valid(MainDB.DB_DATE_RELEASED, rel),
            *_period(rel, year, month),
        ]
    return base + [
        _valid(MainDB.DB_DATE_RECEIVED_CENT, rec),
        *_period(rec, year, month),
    ]


# ── 1. Company search (autocomplete) ─────────────────────────
def search_companies(db: Session, q: str, limit: int = 15) -> list:
    q = (q or "").strip()
    if len(q) < 2:
        return []
    cname = func.trim(MainDB.DB_EST_LTO_COMP)
    pattern = (
        "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )
    rows = (
        db.query(
            _ckey().label("ckey"),
            func.min(cname).label("name"),
            func.count(MainDB.DB_ID).label("n"),
        )
        .filter(
            MainDB.DB_EST_LTO_COMP.isnot(None),
            cname != "",
            cname.ilike(pattern, escape="\\"),
        )
        .group_by(_ckey())
        .order_by(func.count(MainDB.DB_ID).desc(), func.min(cname))
        .limit(limit)
        .all()
    )
    return [{"company": r.name, "applications": int(r.n)} for r in rows]


# ── 2. Monitoring summary ────────────────────────────────────
def get_company_monitoring(
    db: Session,
    companies: list,
    year: str = "All",
    month: str = "All",
    basis: str = "received",
) -> dict:
    basis = "released" if basis == "released" else "received"
    keys = _norms(companies)
    rec, rel = _dates()
    rec_ok = _valid(MainDB.DB_DATE_RECEIVED_CENT, rec)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)
    days = _workdays(rec, rel)
    charter = MainDB.DB_TIMELINE_CITIZEN_CHARTER
    in_company = _in_companies(keys)

    # Display names of the selected companies (one per company key)
    name_rows = (
        db.query(
            _ckey().label("ckey"),
            func.min(func.trim(MainDB.DB_EST_LTO_COMP)).label("name"),
        )
        .filter(in_company)
        .group_by(_ckey())
        .all()
    )
    name_by_key = {_norm(r.ckey): r.name for r in name_rows}
    company_names = [name_by_key.get(k) or k for k in keys]
    display_name = (
        company_names[0]
        if len(company_names) == 1
        else f"{len(company_names)} companies"
    )

    # Received in the period
    received = (
        db.query(func.count(MainDB.DB_ID))
        .filter(in_company, rec_ok, *_period(rec, year, month))
        .scalar()
        or 0
    )
    still_open = (
        db.query(func.count(MainDB.DB_ID))
        .filter(
            in_company,
            rec_ok,
            *_period(rec, year, month),
            or_(not_(_completed()), not_(rel_ok)),
        )
        .scalar()
        or 0
    )

    # Processed in the period (+ TAT stats, valid when release is not before receipt)
    tat_ok = and_(rec_ok, rel >= rec)
    p = (
        db.query(
            func.count(MainDB.DB_ID),
            func.sum(case((tat_ok, 1), else_=0)),
            func.avg(case((tat_ok, days))),
            func.min(case((tat_ok, days))),
            func.max(case((tat_ok, days))),
            func.sum(case((and_(tat_ok, charter > 0, days <= charter), 1), else_=0)),
            func.sum(case((and_(tat_ok, charter > 0, days > charter), 1), else_=0)),
        )
        .filter(in_company, _completed(), rel_ok, *_period(rel, year, month))
        .one()
    )
    processed = int(p[0] or 0)
    tat_count = int(p[1] or 0)
    within = int(p[5] or 0)
    beyond = int(p[6] or 0)

    # Per month (selected year) or per year (All)
    by_year = year in (None, "", "All")
    rec_grp = (func.year(rec) if by_year else func.month(rec)).label("grp")
    rel_grp = (func.year(rel) if by_year else func.month(rel)).label("grp")
    done = and_(_completed(), rel_ok)

    def blank():
        return {
            "received": 0,
            "processed": 0,
            "avg_tat": None,
            # of the applications RECEIVED in the period: how many are released
            "released_of_received": 0,
            "avg_tat_received": None,
        }

    rec_rows = (
        db.query(
            rec_grp,
            func.count(MainDB.DB_ID).label("n"),
            func.sum(case((done, 1), else_=0)).label("rel"),
            func.avg(case((and_(done, tat_ok), days))).label("avg"),
        )
        .filter(in_company, rec_ok, *_period(rec, year, month))
        .group_by("grp")
        .all()
    )
    rel_rows = (
        db.query(
            rel_grp,
            func.count(MainDB.DB_ID).label("n"),
            func.avg(case((tat_ok, days))).label("avg"),
        )
        .filter(in_company, _completed(), rel_ok, *_period(rel, year, month))
        .group_by("grp")
        .all()
    )
    buckets = {}
    for r in rec_rows:
        if r.grp is not None:
            b = buckets.setdefault(int(r.grp), blank())
            b["received"] = int(r.n)
            b["released_of_received"] = int(r.rel or 0)
            b["avg_tat_received"] = _r1(r.avg)
    for r in rel_rows:
        if r.grp is not None:
            b = buckets.setdefault(int(r.grp), blank())
            b["processed"] = int(r.n)
            b["avg_tat"] = _r1(r.avg)
    if not by_year:
        months = [int(month)] if month not in (None, "", "All") else range(1, 13)
        for m in months:
            buckets.setdefault(m, blank())
    periods = [
        {"label": str(k) if by_year else MONTH_ABBR[k], "key": k, **buckets[k]}
        for k in sorted(buckets)
    ]

    # Totals for the "received" view
    rc = (
        db.query(
            func.sum(case((done, 1), else_=0)),
            func.avg(case((and_(done, tat_ok), days))),
        )
        .filter(in_company, rec_ok, *_period(rec, year, month))
        .one()
    )

    # Evaluators (for the chosen basis)
    ev1 = _evaluator_subquery(db)
    ev_rows = (
        db.query(
            ev1.c.user_id.label("user_id"),
            func.max(ev1.c.user_name).label("uname"),
            func.count(MainDB.DB_ID).label("n"),
            func.avg(case((and_(_completed(), rel_ok, tat_ok), days))).label("avg"),
        )
        .select_from(MainDB)
        .outerjoin(ev1, ev1.c.main_db_id == MainDB.DB_ID)
        .filter(*_scope(basis, year, month, keys))
        .group_by(ev1.c.user_id)
        .all()
    )
    names = _names(db, [r.user_id for r in ev_rows])
    evaluators = []
    for r in ev_rows:
        e = _evaluator(r.user_id, r.uname, names)
        e.update({"count": int(r.n), "avg_tat": _r1(r.avg)})
        evaluators.append(e)
    evaluators.sort(key=lambda x: (x["unassigned"], -x["count"], x["code"]))

    return {
        "company": display_name,
        "companies": company_names,
        "year": year,
        "month": month,
        "basis": basis,
        "summary": {
            "received": int(received),
            "processed": processed,
            "still_open": int(still_open),
            "avg_tat": _r1(p[2]),
            "fastest_tat": int(p[3]) if p[3] is not None else None,
            "slowest_tat": int(p[4]) if p[4] is not None else None,
            "tat_count": tat_count,
            "within": within,
            "beyond": beyond,
            "no_charter": tat_count - within - beyond,
            "released_of_received": int(rc[0] or 0),
            "avg_tat_received": _r1(rc[1]),
        },
        "periods": periods,
        "evaluators": evaluators,
        "formula": FORMULA,
    }


# ── 3. Application list with TAT and evaluator ───────────────
def get_company_records(
    db: Session,
    companies: list,
    year: str = "All",
    month: str = "All",
    basis: str = "received",
    user_id: str = None,
    search: str = None,
    sort: str = "received",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    basis = "released" if basis == "released" else "received"
    keys = _norms(companies)
    rec, rel = _dates()
    rec_ok = _valid(MainDB.DB_DATE_RECEIVED_CENT, rec)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)
    done = and_(_completed(), rel_ok)

    # End of the TAT window: release date when released, today when still open
    end = case((done, rel), (not_(_completed()), func.curdate()), else_=None)
    days = case(
        (and_(rec_ok, end.isnot(None), end >= rec), _workdays(rec, end)), else_=None
    )

    ev1 = _evaluator_subquery(db)

    def scoped(q):
        q = (
            q.select_from(MainDB)
            .outerjoin(ev1, ev1.c.main_db_id == MainDB.DB_ID)
            .filter(*_scope(basis, year, month, keys))
        )
        if user_id == "none":
            q = q.filter(ev1.c.user_id.is_(None))
        elif user_id not in (None, ""):
            q = q.filter(ev1.c.user_id == int(user_id))
        if search:
            like = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    func.concat(MainDB.DB_DTN, "").like(like),
                    MainDB.DB_PROD_BR_NAME.ilike(like),
                    MainDB.DB_PROD_GEN_NAME.ilike(like),
                )
            )
        return q

    total = scoped(db.query(func.count(MainDB.DB_ID))).scalar() or 0

    order = (
        [days.desc(), MainDB.DB_ID.asc()]
        if sort == "tat"
        else [rec.desc(), MainDB.DB_ID.desc()]
    )
    rows = (
        scoped(
            db.query(
                MainDB.DB_ID.label("id"),
                MainDB.DB_DTN.label("dtn"),
                MainDB.DB_PROD_BR_NAME.label("brand"),
                MainDB.DB_PROD_GEN_NAME.label("generic"),
                MainDB.DB_APP_TYPE.label("app_type"),
                MainDB.DB_ENTRY_TYPE.label("entry_type"),
                MainDB.DB_APP_STATUS.label("status"),
                MainDB.DB_TYPE_DOC_RELEASED.label("doc"),
                MainDB.DB_DATE_RECEIVED_CENT.label("received"),
                MainDB.DB_DATE_RELEASED.label("released"),
                MainDB.DB_TIMELINE_CITIZEN_CHARTER.label("charter"),
                days.label("days"),
                case((done, 1), else_=0).label("is_released"),
                case((_completed(), 0), else_=1).label("is_open"),
                ev1.c.user_id.label("ev_id"),
                ev1.c.user_name.label("ev_name"),
            )
        )
        .order_by(*order)
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )
    names = _names(db, [r.ev_id for r in rows])

    def _d(v):
        s = str(v)[:10] if v else None
        return None if s in (None, "", "N/A") else s

    data = []
    for r in rows:
        tat = int(r.days) if r.days is not None else None
        charter = int(r.charter) if r.charter else None
        if r.is_released:
            state = "Released"
        elif r.is_open:
            state = "Ongoing"
        else:
            state = "No release date"
        if tat is None or not charter:
            timeline = "N/A"
        else:
            timeline = "Within" if tat <= charter else "Beyond"
        brand, generic = r.brand or "", r.generic or ""
        data.append(
            {
                "db_id": r.id,
                "dtn": str(r.dtn) if r.dtn else None,
                "drug": (
                    f"{brand} ({generic})"
                    if brand and generic
                    else brand or generic or None
                ),
                "app_type": (r.app_type or "").strip() or None,
                "entry_type": (r.entry_type or "").strip() or None,
                "status": r.status or None,
                "doc": r.doc or None,
                "date_received": _d(r.received),
                "date_released": _d(r.released),
                "state": state,
                "tat_days": tat,
                "charter_days": charter,
                "timeline": timeline,
                "evaluator": _evaluator(r.ev_id, r.ev_name, names),
            }
        )

    return {"total": int(total), "page": page, "page_size": page_size, "data": data}


# ── 4. Released applications by type of document released ────
def get_company_released_docs(
    db: Session,
    companies: list,
    year: str = "All",
    month: str = "All",
    view: str = "released",
) -> dict:
    """Breakdown of the released applications by DB_TYPE_DOC_RELEASED.

    view = "received": received in the period AND already released (any date).
    view = "released": released (processed) in the period.
    Same filters as the numbers shown in the monitoring table.
    """
    view = "received" if view == "received" else "released"
    keys = _norms(companies)
    rec, rel = _dates()
    rec_ok = _valid(MainDB.DB_DATE_RECEIVED_CENT, rec)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)
    done = and_(_completed(), rel_ok)
    tat_ok = and_(rec_ok, rel >= rec)
    days = _workdays(rec, rel)

    if view == "received":
        period = [rec_ok, *_period(rec, year, month)]
    else:
        period = [*_period(rel, year, month)]

    doc = func.coalesce(
        func.nullif(func.trim(MainDB.DB_TYPE_DOC_RELEASED), ""), "No document type"
    )
    rows = (
        db.query(
            doc.label("doc"),
            func.count(MainDB.DB_ID).label("n"),
            func.avg(case((tat_ok, days))).label("avg"),
        )
        .filter(_in_companies(keys), done, *period)
        .group_by(doc)
        .order_by(func.count(MainDB.DB_ID).desc(), doc)
        .all()
    )
    total = sum(int(r.n) for r in rows)
    return {
        "view": view,
        "year": year,
        "month": month,
        "total": total,
        "data": [
            {
                "doc": r.doc,
                "count": int(r.n),
                "percent": round(int(r.n) * 100 / total, 1) if total else 0,
                "avg_tat": _r1(r.avg),
            }
            for r in rows
        ],
    }


# ── 5. Applications of one document type (expand sa modal) ───
def get_company_released_doc_records(
    db: Session,
    companies: list,
    doc: str,
    year: str = "All",
    month: str = "All",
    view: str = "released",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """Applications behind one row of get_company_released_docs (same filters)."""
    view = "received" if view == "received" else "released"
    keys = _norms(companies)
    rec, rel = _dates()
    rec_ok = _valid(MainDB.DB_DATE_RECEIVED_CENT, rec)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)
    done = and_(_completed(), rel_ok)
    days = case((and_(rec_ok, rel >= rec), _workdays(rec, rel)), else_=None)

    if view == "received":
        period = [rec_ok, *_period(rec, year, month)]
    else:
        period = [*_period(rel, year, month)]

    docx = func.coalesce(
        func.nullif(func.trim(MainDB.DB_TYPE_DOC_RELEASED), ""), "No document type"
    )
    ev1 = _evaluator_subquery(db)

    def scoped(q):
        return (
            q.select_from(MainDB)
            .outerjoin(ev1, ev1.c.main_db_id == MainDB.DB_ID)
            .filter(_in_companies(keys), done, docx == doc, *period)
        )

    total = scoped(db.query(func.count(MainDB.DB_ID))).scalar() or 0
    rows = (
        scoped(
            db.query(
                MainDB.DB_ID.label("id"),
                MainDB.DB_DTN.label("dtn"),
                MainDB.DB_PROD_BR_NAME.label("brand"),
                MainDB.DB_PROD_GEN_NAME.label("generic"),
                MainDB.DB_DATE_RECEIVED_CENT.label("received"),
                MainDB.DB_DATE_RELEASED.label("released"),
                MainDB.DB_TIMELINE_CITIZEN_CHARTER.label("charter"),
                days.label("days"),
                ev1.c.user_id.label("ev_id"),
                ev1.c.user_name.label("ev_name"),
            )
        )
        .order_by(rec.desc(), MainDB.DB_ID.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )
    names = _names(db, [r.ev_id for r in rows])

    def _d(v):
        s = str(v)[:10] if v else None
        return None if s in (None, "", "N/A") else s

    data = []
    for r in rows:
        tat = int(r.days) if r.days is not None else None
        charter = int(r.charter) if r.charter else None
        if tat is None or not charter:
            timeline = "N/A"
        else:
            timeline = "Within" if tat <= charter else "Beyond"
        brand, generic = r.brand or "", r.generic or ""
        data.append(
            {
                "db_id": r.id,
                "dtn": str(r.dtn) if r.dtn else None,
                "drug": (
                    f"{brand} ({generic})"
                    if brand and generic
                    else brand or generic or None
                ),
                "date_received": _d(r.received),
                "date_released": _d(r.released),
                "tat_days": tat,
                "charter_days": charter,
                "timeline": timeline,
                "evaluator": _evaluator(r.ev_id, r.ev_name, names),
            }
        )
    return {"total": int(total), "page": page, "page_size": page_size, "data": data}
