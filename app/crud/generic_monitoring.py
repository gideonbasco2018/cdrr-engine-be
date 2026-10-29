# app/crud/generic_monitoring.py
#
# Generic-name monitoring: pick one or more generic names (e.g. the cancer
# drugs) and see how many applications are pending / registered per generic.
#
#   - generic key : UPPER(TRIM(DB_PROD_GEN_NAME))
#   - pending     : status is not COMPLETED
#   - registered  : COMPLETED and Type of Doc Released = CPR
#   - lod         : COMPLETED and Type of Doc Released = LOD
#   - other       : any other COMPLETED application
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.models.main_db import MainDB


# ── Shared expressions ───────────────────────────────────────
def _gkey():
    return func.upper(func.trim(MainDB.DB_PROD_GEN_NAME))


def _norms(generics) -> list:
    if isinstance(generics, str):
        generics = [generics]
    seen, out = set(), []
    for g in generics or []:
        k = (g or "").strip().upper()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _completed():
    status = func.upper(func.trim(func.coalesce(MainDB.DB_APP_STATUS, "")))
    return status == "COMPLETED"


def _doc():
    return func.upper(func.trim(func.coalesce(MainDB.DB_TYPE_DOC_RELEASED, "")))


def _is_pending():
    return ~_completed()


def _is_registered():
    return and_(_completed(), _doc() == "CPR")


def _is_lod():
    return and_(_completed(), _doc() == "LOD")


def _is_other():
    return and_(_completed(), _doc() != "CPR", _doc() != "LOD")


def _sum(cond):
    return func.sum(case((cond, 1), else_=0))


# ── 1. Generic name search (autocomplete) ────────────────────
def search_generics(db: Session, q: str, limit: int = 30) -> list:
    q = (q or "").strip()
    if len(q) < 2:
        return []
    gname = func.trim(MainDB.DB_PROD_GEN_NAME)
    pattern = (
        "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )
    rows = (
        db.query(
            _gkey().label("gkey"),
            func.min(gname).label("name"),
            func.count(MainDB.DB_ID).label("n"),
        )
        .filter(
            MainDB.DB_PROD_GEN_NAME.isnot(None),
            gname != "",
            gname.ilike(pattern, escape="\\"),
        )
        .group_by(_gkey())
        .order_by(func.count(MainDB.DB_ID).desc(), func.min(gname))
        .limit(limit)
        .all()
    )
    return [{"generic": r.name, "applications": int(r.n)} for r in rows]


# ── 2. Summary per generic ───────────────────────────────────
def get_generic_summary(db: Session, generics: list) -> dict:
    keys = _norms(generics)
    if not keys:
        return {"generics": [], "totals": _totals([])}

    rows = (
        db.query(
            _gkey().label("gkey"),
            func.min(func.trim(MainDB.DB_PROD_GEN_NAME)).label("name"),
            func.count(MainDB.DB_ID).label("total"),
            _sum(_is_pending()).label("pending"),
            _sum(_is_registered()).label("registered"),
            _sum(_is_lod()).label("lod"),
            _sum(_is_other()).label("other"),
        )
        .filter(_gkey().in_(keys))
        .group_by(_gkey())
        .all()
    )
    data = [
        {
            "generic": r.name,
            "total": int(r.total or 0),
            "pending": int(r.pending or 0),
            "registered": int(r.registered or 0),
            "lod": int(r.lod or 0),
            "other": int(r.other or 0),
        }
        for r in rows
    ]
    data.sort(key=lambda x: (-x["total"], x["generic"] or ""))
    return {"generics": data, "totals": _totals(data)}


def _totals(data: list) -> dict:
    return {
        k: sum(d[k] for d in data)
        for k in ("total", "pending", "registered", "lod", "other")
    }


# ── 3. Application list ──────────────────────────────────────
def get_generic_records(
    db: Session,
    generics: list,
    group: str = "all",
    search: str = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    keys = _norms(generics)
    if not keys:
        return {"total": 0, "page": page, "page_size": page_size, "data": []}

    def scoped(q):
        q = q.filter(_gkey().in_(keys))
        if group == "pending":
            q = q.filter(_is_pending())
        elif group == "registered":
            q = q.filter(_is_registered())
        elif group == "lod":
            q = q.filter(_is_lod())
        elif group == "other":
            q = q.filter(_is_other())
        if search:
            like = f"%{search.strip()}%"
            q = q.filter(
                or_(
                    func.concat(MainDB.DB_DTN, "").like(like),
                    MainDB.DB_PROD_BR_NAME.ilike(like),
                    MainDB.DB_PROD_GEN_NAME.ilike(like),
                    MainDB.DB_EST_LTO_COMP.ilike(like),
                )
            )
        return q

    total = scoped(db.query(func.count(MainDB.DB_ID))).scalar() or 0
    rows = (
        scoped(
            db.query(
                MainDB.DB_ID.label("id"),
                MainDB.DB_DTN.label("dtn"),
                MainDB.DB_PROD_GEN_NAME.label("generic"),
                MainDB.DB_PROD_BR_NAME.label("brand"),
                MainDB.DB_EST_LTO_COMP.label("company"),
                MainDB.DB_APP_STATUS.label("status"),
                MainDB.DB_TYPE_DOC_RELEASED.label("doc"),
                MainDB.DB_DATE_RECEIVED_CENT.label("received"),
                MainDB.DB_DATE_RELEASED.label("released"),
            )
        )
        .order_by(MainDB.DB_ID.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _d(v):
        s = str(v)[:10] if v else None
        return None if s in (None, "", "N/A") else s

    data = [
        {
            "db_id": r.id,
            "dtn": str(r.dtn) if r.dtn else None,
            "generic": (r.generic or "").strip() or None,
            "brand": (r.brand or "").strip() or None,
            "company": (r.company or "").strip() or None,
            "status": r.status or None,
            "doc": (r.doc or "").strip() or None,
            "date_received": _d(r.received),
            "date_released": _d(r.released),
        }
        for r in rows
    ]
    return {"total": int(total), "page": page, "page_size": page_size, "data": data}
