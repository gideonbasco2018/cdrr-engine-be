# app/crud/top_companies.py
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs
from app.models.user import User
from app.crud.analytics import _doc_key_expr, _status_key_expr

# Matches the evaluation step label (case-insensitive).
EVALUATION_STEP_PATTERN = "%quality evaluation%"


def _apps_subquery(db: Session, year, month, prescription, basis):
    """Applications (with a company) received/released in the period."""
    col = (
        MainDB.DB_DATE_RELEASED if basis == "released" else MainDB.DB_DATE_RECEIVED_CENT
    )
    d = func.str_to_date(func.left(col, 10), "%Y-%m-%d")
    ckey = func.upper(func.trim(MainDB.DB_EST_LTO_COMP))
    cname = func.trim(MainDB.DB_EST_LTO_COMP)

    q = db.query(
        MainDB.DB_ID.label("id"),
        ckey.label("ckey"),
        cname.label("cname"),
    ).filter(
        MainDB.DB_EST_LTO_COMP.isnot(None),
        cname != "",
        col.isnot(None),
        col != "",
        col != "N/A",
        d.isnot(None),
        func.year(d) == int(year),
    )
    if month != "All":
        q = q.filter(func.month(d) == int(month))  # 1-12
    if prescription != "All":
        q = q.filter(MainDB.DB_PROD_CLASS_PRESCRIP == prescription)
    return q.subquery()


def _evaluator_subquery(db: Session):
    """One evaluator per application: the latest Quality Evaluation row
    that was not reassigned. Rerouted rows ARE counted; reassigned rows are
    skipped because a newer row already holds the new assignee."""
    rn = func.row_number().over(
        partition_by=ApplicationLogs.main_db_id,
        order_by=(ApplicationLogs.del_index.desc(), ApplicationLogs.id.desc()),
    )
    ev = (
        db.query(
            ApplicationLogs.main_db_id.label("main_db_id"),
            ApplicationLogs.user_id.label("user_id"),
            ApplicationLogs.user_name.label("user_name"),
            rn.label("rn"),
        )
        .filter(
            ApplicationLogs.application_step.ilike(EVALUATION_STEP_PATTERN),
            ApplicationLogs.reassigned_at.is_(None),
            ApplicationLogs.reassigned_by_user_id.is_(None),
        )
        .subquery()
    )
    return (
        db.query(ev.c.main_db_id, ev.c.user_id, ev.c.user_name)
        .filter(ev.c.rn == 1)
        .subquery()
    )


def _full_name(u) -> str:
    first = (getattr(u, "first_name", None) or "").strip()
    last = (getattr(u, "last_name", None) or "").strip()
    if first or last:
        return f"{first} {last}".strip()
    for attr in ("full_name", "fullname", "name"):
        v = getattr(u, attr, None)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def get_top_companies(
    db: Session,
    year: int,
    month: str = "All",
    top: int = 10,
    prescription: str = "All",
    basis: str = "received",
) -> dict:
    basis = "released" if basis == "released" else "received"
    apps = _apps_subquery(db, year, month, prescription, basis)

    total_apps = db.query(func.count(apps.c.id)).scalar() or 0
    total_companies = db.query(func.count(func.distinct(apps.c.ckey))).scalar() or 0

    top_rows = (
        db.query(
            apps.c.ckey.label("ckey"),
            func.min(apps.c.cname).label("name"),
            func.count(apps.c.id).label("n"),
        )
        .group_by(apps.c.ckey)
        .order_by(func.count(apps.c.id).desc(), func.min(apps.c.cname))
        .limit(top)
        .all()
    )

    matched_steps = [
        r[0]
        for r in db.query(ApplicationLogs.application_step)
        .filter(ApplicationLogs.application_step.ilike(EVALUATION_STEP_PATTERN))
        .distinct()
        .all()
        if r[0]
    ]

    keys = [r.ckey for r in top_rows]
    if not keys:
        return {
            "total_apps": int(total_apps),
            "total_companies": int(total_companies),
            "top_apps": 0,
            "matched_steps": matched_steps,
            "data": [],
        }

    ev1 = _evaluator_subquery(db)
    rows = (
        db.query(
            apps.c.ckey.label("ckey"),
            ev1.c.user_id.label("user_id"),
            func.max(ev1.c.user_name).label("uname"),
            func.count(apps.c.id).label("n"),
        )
        .outerjoin(ev1, ev1.c.main_db_id == apps.c.id)
        .filter(apps.c.ckey.in_(keys))
        .group_by(apps.c.ckey, ev1.c.user_id)
        .all()
    )

    # Real names from the users table
    uids = {r.user_id for r in rows if r.user_id is not None}
    names = {}
    if uids:
        for u in db.query(User).filter(User.id.in_(uids)).all():
            names[u.id] = _full_name(u)

    by_key = {}
    for r in rows:
        unassigned = r.user_id is None
        code = (
            "Unassigned"
            if unassigned
            else ((r.uname or "").strip() or f"User #{r.user_id}")
        )
        by_key.setdefault(r.ckey, []).append(
            {
                "user_id": r.user_id,
                "code": code,
                "name": code,  # kept for compatibility
                "full_name": "" if unassigned else names.get(r.user_id, ""),
                "unassigned": unassigned,
                "count": int(r.n),
            }
        )

    data = []
    for rank, t in enumerate(top_rows, start=1):
        evs = sorted(
            by_key.get(t.ckey, []),
            key=lambda x: (x["unassigned"], -x["count"], x["code"]),
        )
        data.append(
            {"rank": rank, "company": t.name, "count": int(t.n), "evaluators": evs}
        )

    return {
        "total_apps": int(total_apps),
        "total_companies": int(total_companies),
        "top_apps": sum(x["count"] for x in data),
        "matched_steps": matched_steps,
        "data": data,
    }


def get_company_records(
    db: Session,
    year: int,
    month: str = "All",
    prescription: str = "All",
    basis: str = "received",
    company: str = "",
    user_id: str = None,
    page: int = 1,
    page_size: int = 50,
    search: str = None,
    status: str = None,
    doc_type: str = None,
) -> dict:
    """Applications behind a company row (user_id=None) or an evaluator row
    (user_id="123", or "none" for Unassigned). Same rules as get_top_companies,
    so the count always matches the number that was clicked."""
    basis = "released" if basis == "released" else "received"
    apps = _apps_subquery(db, year, month, prescription, basis)
    ev1 = _evaluator_subquery(db)
    ckey = (company or "").strip().upper()

    doc_key = _doc_key_expr()
    status_key = _status_key_expr()
    rec_date = func.str_to_date(func.left(MainDB.DB_DATE_RECEIVED_CENT, 10), "%Y-%m-%d")

    def scoped(q, use_status=True, use_doc=True):
        q = (
            q.select_from(MainDB)
            .join(apps, apps.c.id == MainDB.DB_ID)
            .outerjoin(ev1, ev1.c.main_db_id == MainDB.DB_ID)
            .filter(apps.c.ckey == ckey)
        )
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
        )
    )
    total = rows_q.count()
    rows = (
        rows_q.order_by(rec_date.asc(), MainDB.DB_ID.asc())
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
            }
            for r in rows
        ],
    }
