# app/crud/fastest_processing.py
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.main_db import MainDB
from app.models.user import User
from app.crud.top_companies import _evaluator_subquery, _full_name
from app.crud.analytics import _doc_key_expr, _status_key_expr


def _dates():
    rec = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")
    rel = func.str_to_date(func.left(MainDB.DB_DATE_RELEASED, 10), "%Y-%m-%d")
    return rec, rel


def _workdays(start, end):
    """Working days (Mon-Fri) after `start`, up to and including `end`.
    Same day = 0. Fri -> Mon = 1. Mon -> next Mon = 5.
    weekday(): Mon=0 ... Sat=5, Sun=6."""
    n = func.datediff(end, start)
    ws = func.weekday(start)
    sat = func.floor((ws + n - 5) / 7.0) - func.floor((ws - 5) / 7.0)
    sun = func.floor((ws + n - 6) / 7.0) - func.floor((ws - 6) / 7.0)
    return n - sat - sun


def _is_cpr():
    return MainDB.DB_TYPE_DOC_RELEASED.ilike("%CPR%")


def _is_cert():
    return func.lower(func.trim(MainDB.DB_TYPE_DOC_RELEASED)).in_(
        ["cert", "certificate"]
    )


def _period_filters(year, month):
    rec, rel = _dates()
    f = [
        MainDB.DB_DATE_RECEIVED_CENT.isnot(None),
        MainDB.DB_DATE_RECEIVED_CENT != "",
        MainDB.DB_DATE_RECEIVED_CENT != "N/A",
        MainDB.DB_DATE_RELEASED.isnot(None),
        MainDB.DB_DATE_RELEASED != "",
        MainDB.DB_DATE_RELEASED != "N/A",
        rec.isnot(None),
        rel.isnot(None),
        func.year(rec) >= 2000,
        func.year(rel) == int(year),
        rel >= rec,
    ]
    if month != "All":
        f.append(func.month(rel) == int(month))  # 1-12
    return f


def _r1(v):
    return round(float(v), 1) if v is not None else None


def _names(db: Session, user_ids) -> dict:
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    return {u.id: _full_name(u) for u in db.query(User).filter(User.id.in_(ids)).all()}


def _evaluator(user_id, uname, names) -> dict:
    if user_id is None:
        return {
            "user_id": None,
            "code": "Unassigned",
            "full_name": "",
            "unassigned": True,
        }
    code = (uname or "").strip() or f"User #{user_id}"
    return {
        "user_id": user_id,
        "code": code,
        "full_name": names.get(user_id, ""),
        "unassigned": False,
    }


# ── Fastest applications ──────────────────────────────────────
def get_fastest_applications(
    db: Session, year: int, month: str = "All", top: int = 10, doc: str = "cpr"
) -> dict:
    rec, rel = _dates()
    days = _workdays(rec, rel)
    if doc == "cert":
        doc_cond = _is_cert()
    elif doc == "both":
        doc_cond = or_(_is_cpr(), _is_cert())
    else:
        doc = "cpr"
        doc_cond = _is_cpr()
    scope = [*_period_filters(year, month), doc_cond]

    stats = (
        db.query(
            func.count(MainDB.DB_ID),
            func.avg(days),
            func.min(days),
        )
        .filter(*scope)
        .one()
    )

    ev1 = _evaluator_subquery(db)
    rows = (
        db.query(
            MainDB.DB_ID.label("id"),
            MainDB.DB_DTN.label("dtn"),
            MainDB.DB_EST_LTO_COMP.label("company"),
            MainDB.DB_PROD_BR_NAME.label("brand"),
            MainDB.DB_PROD_GEN_NAME.label("generic"),
            MainDB.DB_TYPE_DOC_RELEASED.label("doc"),
            MainDB.DB_DATE_RECEIVED_CENT.label("received"),
            MainDB.DB_DATE_RELEASED.label("released"),
            days.label("days"),
            ev1.c.user_id.label("user_id"),
            ev1.c.user_name.label("user_name"),
        )
        .outerjoin(ev1, ev1.c.main_db_id == MainDB.DB_ID)
        .filter(*scope)
        .order_by(days.asc(), rel.asc(), MainDB.DB_ID.asc())
        .limit(top)
        .all()
    )

    names = _names(db, [r.user_id for r in rows])

    def _d(v):
        return str(v)[:10] if v else None

    return {
        "doc": doc,
        "total": int(stats[0] or 0),
        "avg_days": _r1(stats[1]),
        "fastest_days": int(stats[2]) if stats[2] is not None else None,
        "data": [
            {
                "rank": i,
                "db_id": r.id,
                "dtn": str(r.dtn) if r.dtn else None,
                "company": (r.company or "").strip(),
                "brand": r.brand or None,
                "generic": r.generic or None,
                "doc": r.doc or None,
                "received": _d(r.received),
                "released": _d(r.released),
                "days": int(r.days),
                "evaluator": _evaluator(r.user_id, r.user_name, names),
            }
            for i, r in enumerate(rows, start=1)
        ],
    }


# ── Fastest companies (CPR + Cert) ────────────────────────────
def get_fastest_companies(
    db: Session, year: int, month: str = "All", top: int = 10, min_apps: int = 3
) -> dict:
    rec, rel = _dates()
    days = _workdays(rec, rel)
    cname = func.trim(MainDB.DB_EST_LTO_COMP)
    ckey = func.upper(cname)
    is_cpr, is_cert = _is_cpr(), _is_cert()

    apps = (
        db.query(
            MainDB.DB_ID.label("id"),
            ckey.label("ckey"),
            cname.label("cname"),
            days.label("days"),
            case((is_cpr, 1), else_=0).label("is_cpr"),
            case((is_cert, 1), else_=0).label("is_cert"),
        )
        .filter(
            *_period_filters(year, month),
            MainDB.DB_EST_LTO_COMP.isnot(None),
            cname != "",
            or_(is_cpr, is_cert),
        )
        .subquery()
    )

    total_apps = db.query(func.count(apps.c.id)).scalar() or 0
    overall_avg = db.query(func.avg(apps.c.days)).scalar()

    qualifying = (
        db.query(apps.c.ckey)
        .group_by(apps.c.ckey)
        .having(func.count(apps.c.id) >= min_apps)
        .subquery()
    )
    total_companies = db.query(func.count()).select_from(qualifying).scalar() or 0

    top_rows = (
        db.query(
            apps.c.ckey.label("ckey"),
            func.min(apps.c.cname).label("name"),
            func.count(apps.c.id).label("n"),
            func.avg(apps.c.days).label("avg"),
            func.min(apps.c.days).label("fastest"),
            func.sum(apps.c.is_cpr).label("cpr"),
            func.sum(apps.c.is_cert).label("cert"),
        )
        .group_by(apps.c.ckey)
        .having(func.count(apps.c.id) >= min_apps)
        .order_by(
            func.avg(apps.c.days).asc(),
            func.count(apps.c.id).desc(),
            func.min(apps.c.cname),
        )
        .limit(top)
        .all()
    )

    keys = [r.ckey for r in top_rows]
    by_key = {}
    if keys:
        ev1 = _evaluator_subquery(db)
        ev_rows = (
            db.query(
                apps.c.ckey.label("ckey"),
                ev1.c.user_id.label("user_id"),
                func.max(ev1.c.user_name).label("uname"),
                func.count(apps.c.id).label("n"),
                func.avg(apps.c.days).label("avg"),
                func.sum(apps.c.is_cpr).label("cpr"),
                func.sum(apps.c.is_cert).label("cert"),
            )
            .outerjoin(ev1, ev1.c.main_db_id == apps.c.id)
            .filter(apps.c.ckey.in_(keys))
            .group_by(apps.c.ckey, ev1.c.user_id)
            .all()
        )
        names = _names(db, [r.user_id for r in ev_rows])
        for r in ev_rows:
            e = _evaluator(r.user_id, r.uname, names)
            e.update(
                {
                    "count": int(r.n),
                    "avg_days": _r1(r.avg),
                    "cpr": int(r.cpr or 0),
                    "cert": int(r.cert or 0),
                }
            )
            by_key.setdefault(r.ckey, []).append(e)

    data = []
    for rank, t in enumerate(top_rows, start=1):
        evs = sorted(
            by_key.get(t.ckey, []),
            key=lambda x: (x["unassigned"], -x["count"], x["code"]),
        )
        data.append(
            {
                "rank": rank,
                "company": t.name,
                "count": int(t.n),
                "cpr": int(t.cpr or 0),
                "cert": int(t.cert or 0),
                "avg_days": _r1(t.avg),
                "fastest_days": int(t.fastest),
                "evaluators": evs,
            }
        )

    return {
        "total_apps": int(total_apps),
        "total_companies": int(total_companies),
        "overall_avg_days": _r1(overall_avg),
        "min_apps": min_apps,
        "data": data,
    }


def _doc_cond(doc: str):
    if doc == "cert":
        return _is_cert()
    if doc == "cpr":
        return _is_cpr()
    return or_(_is_cpr(), _is_cert())


def get_fastest_records(
    db: Session,
    year: int,
    month: str = "All",
    doc: str = "both",
    company: str = None,
    user_id: str = None,
    page: int = 1,
    page_size: int = 50,
    search: str = None,
    status: str = None,
    doc_type: str = None,
    received_from: str = None,
    received_to: str = None,
    released_from: str = None,
    released_to: str = None,
) -> dict:
    """Applications behind a Fastest Processing number.
    company=None -> all companies; user_id=None -> all evaluators,
    user_id="none" -> Unassigned. Same period / doc / evaluator rules as
    the Fastest views, so the count always matches the number clicked."""
    rec, rel = _dates()
    days = _workdays(rec, rel)
    ev1 = _evaluator_subquery(db)
    doc_key = _doc_key_expr()
    status_key = _status_key_expr()
    ckey = func.upper(func.trim(MainDB.DB_EST_LTO_COMP))
    base = [*_period_filters(year, month), _doc_cond(doc)]

    def scoped(q, use_status=True, use_doc=True):
        q = (
            q.select_from(MainDB)
            .outerjoin(ev1, ev1.c.main_db_id == MainDB.DB_ID)
            .filter(*base)
        )
        if company:
            q = q.filter(ckey == company.strip().upper())
        if user_id == "none":
            q = q.filter(ev1.c.user_id.is_(None))
        elif user_id not in (None, ""):
            q = q.filter(ev1.c.user_id == int(user_id))
        if search:
            q = q.filter(func.concat(MainDB.DB_DTN, "").like(f"%{search}%"))
        if use_status and status:
            q = q.filter(status_key == status)
        if use_doc and doc_type:
            q = q.filter(doc_key == doc_type)
        if received_from:
            q = q.filter(rec >= received_from)
        if received_to:
            q = q.filter(rec <= received_to)
        if released_from:
            q = q.filter(rel >= released_from)
        if released_to:
            q = q.filter(rel <= released_to)
        return q

    rows_q = scoped(
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
            MainDB.DB_SECPA_EXP_DATE,
            days.label("days"),
        )
    )
    total = rows_q.count()
    rows = (
        rows_q.order_by(days.asc(), rel.asc(), MainDB.DB_ID.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    status_rows = (
        scoped(
            db.query(status_key.label("k"), func.count(MainDB.DB_ID).label("n")),
            use_status=False,
        )
        .group_by("k")
        .all()
    )
    status_counts = sorted(
        [{"key": r.k, "count": int(r.n or 0)} for r in status_rows],
        key=lambda x: (-x["count"], x["key"]),
    )

    doc_rows = (
        scoped(
            db.query(doc_key.label("k"), func.count(MainDB.DB_ID).label("n")),
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
                "secpa_exp_date": _d(r.DB_SECPA_EXP_DATE),
                "type_doc_released": r.DB_TYPE_DOC_RELEASED or None,
                "app_status": r.DB_APP_STATUS or None,
                "brand_name": r.DB_PROD_BR_NAME or None,
                "generic_name": r.DB_PROD_GEN_NAME or None,
                "days": int(r.days) if r.days is not None else None,
            }
            for r in rows
        ],
    }
