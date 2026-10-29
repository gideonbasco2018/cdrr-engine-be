# app/crud/evaluator_monitoring.py
#
# Evaluators Monitoring: for one evaluator (or checker), how the closed
# applications they handled did per company and per drug (ranked by average
# turnaround time), and how many were received / released per year or month.
#
# Reuses the rules already used by the other analytics views:
#   - company key      : letters and digits only (see _norm)
#   - working days     : Mon-Fri between two dates             (Fastest Processing)
#   - valid date       : readable, year 2000-2100              (Company Monitoring)
#
# Who handled an application: the latest step of the role (Quality Evaluation
# for evaluators, Checking for checkers) that was not reassigned.
# Closed application = has a valid Date Released.
#
# TAT = working days from a START to a FINISH, each with a fallback:
#   START  1st: the start of the first step of the role (Quality Evaluation /
#               Checking) that has a date in the application log
#          2nd: the Date Decked of the application (DB_DATE_DECK)
#   FINISH 1st: the finish of the person's own step in the application log
#          2nd: the Date Released of the application (DB_DATE_RELEASED)
# Each application says where its start and its finish came from ("log" or
# "decked" / "released"), so a reader can tell a log TAT from a fallback one.
# Applications with no usable start or finish are skipped, with the reason.
from types import SimpleNamespace

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs
from app.models.user import User
from app.crud.fastest_processing import _workdays
from app.crud.company_monitoring import (
    MONTH_ABBR,
    _dates,
    _full_name,
    _period,
    _r1,
    _valid,
)

# Only users in these groups may open the page.
ALLOWED_GROUP_IDS = {7, 43}

SKIPPED_LIMIT = 200  # rows of skipped applications sent to the page

# step names are matched with ILIKE, so the PRSDD versions are included
ROLES = {
    "evaluator": {
        "label": "Evaluator",
        "pattern": "%quality evaluation%",
        "step": "Quality Evaluation",
        "before": "Decking",
    },
    "checker": {
        "label": "Checker",
        "pattern": "%checking%",
        "step": "Checking",
        "before": "Quality Evaluation",
    },
}

R_NO_START = "No start date (not in the application log, no valid Date Decked)"
R_NO_END = "No finish date (not in the application log, no valid Date Released)"
R_BEFORE = "Finished before it started"


def _role(role: str) -> str:
    return role if role in ROLES else "evaluator"


def _formula(role: str) -> dict:
    r = ROLES[role]
    who = r["label"].lower()
    return {
        "closed": "Closed application = an application with a valid Date Released.",
        "tat": (
            f"TAT = working days (Monday to Friday) from a start to a finish. "
            f"Start = the start of the first {r['step']} step that has a date "
            f"in the application log; if there is none, the Date Decked of the "
            f"application. Finish = the finish of the {who}'s own {r['step']} "
            f"step in the application log; if there is none, the Date "
            f"Released. Every application shows where its start and its "
            f"finish came from. Same day = 0. Holidays are not deducted."
        ),
        "rank": (
            "Rank 1 = shortest average TAT. Equal averages are ordered by more "
            "applications first, then by name. Every company and drug is "
            "ranked, so check Total Apps: a low number means the rank rests "
            "on few applications."
        ),
        "names": (
            "Company and drug names are matched ignoring capital letters, "
            "spaces and punctuation, so 'Pfizer, Inc.' and 'PFIZER INC' count "
            "as one. The most common spelling is shown. Names with different "
            "letters (a real misspelling) are still counted separately."
        ),
        "person": (
            f"{r['label']} = the user of the latest {r['step']} step that was "
            f"not reassigned. Application logs from before April 2026 mostly "
            f"have no dates, so those applications use the Date Decked and "
            f"the Date Released instead (and say so)."
        ),
        "received": (
            f"Received counts all applications handled by the {who}, open or "
            f"closed. Released counts the applications with a valid Date "
            f"Released."
        ),
    }


# ── Shared expressions ───────────────────────────────────────
def _empty(col):
    """True when the text column holds nothing useful."""
    return or_(col.is_(None), func.trim(col) == "", func.trim(col) == "N/A")


def _norm(col):
    """Name key: capitals, spaces and punctuation are ignored, so
    'Pfizer, Inc.' and 'PFIZER INC' are the same company."""
    return func.regexp_replace(func.upper(col), r"[^\p{L}\p{N}]", "")


def _spelling(col):
    """The name as typed, with line breaks and repeated spaces collapsed."""
    return func.regexp_replace(func.trim(col), r"\s+", " ")


def _ckey():
    return _norm(MainDB.DB_EST_LTO_COMP)


def _gkey():
    return _norm(MainDB.DB_PROD_GEN_NAME)


def _parts(db: Session, role: str, user_id: int) -> SimpleNamespace:
    """Sub-queries and expressions that read one role's steps from the log.
    Only the applications this person ever had a step on are read, which keeps
    the queries fast."""
    L = ApplicationLogs
    pattern = ROLES[role]["pattern"]
    mine = db.query(L.main_db_id).filter(
        L.user_id == user_id, L.application_step.ilike(pattern)
    )

    # the person who handled the app: latest non-reassigned step of the role
    rn = func.row_number().over(
        partition_by=L.main_db_id,
        order_by=(L.del_index.desc(), L.id.desc()),
    )
    ranked_rows = (
        db.query(
            L.main_db_id.label("main_db_id"),
            L.user_id.label("user_id"),
            L.del_index.label("del_index"),
            L.accomplished_date.label("done"),
            rn.label("rn"),
        )
        .filter(
            L.application_step.ilike(pattern),
            L.reassigned_at.is_(None),
            L.reassigned_by_user_id.is_(None),
            L.main_db_id.in_(mine),
        )
        .subquery()
    )
    owner = (
        db.query(
            ranked_rows.c.main_db_id,
            ranked_rows.c.user_id,
            ranked_rows.c.del_index,
            ranked_rows.c.done,
        )
        .filter(ranked_rows.c.rn == 1)
        .subquery()
    )

    # the FIRST step of the role on the app (any person)
    first = (
        db.query(
            L.main_db_id.label("main_db_id"),
            func.min(L.start_date).label("first_start"),
            func.min(L.del_index).label("first_idx"),
        )
        .filter(L.application_step.ilike(pattern), L.main_db_id.in_(mine))
        .group_by(L.main_db_id)
        .subquery()
    )
    # fallbacks that come from the application itself
    rec, rel = _dates()
    deck = func.str_to_date(func.left(MainDB.DB_DATE_DECK, 10), "%Y-%m-%d")
    deck_ok = _valid(MainDB.DB_DATE_DECK, deck)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)

    # START: first dated step of the role in the log, else Date Decked
    # FINISH: the person's own step in the log, else Date Released
    start = func.coalesce(first.c.first_start, case((deck_ok, deck), else_=None))
    end = func.coalesce(owner.c.done, case((rel_ok, rel), else_=None))
    start_src = case(
        (first.c.first_start.isnot(None), "log"),
        (deck_ok, "decked"),
        else_=None,
    )
    end_src = case(
        (owner.c.done.isnot(None), "log"),
        (rel_ok, "released"),
        else_=None,
    )
    return SimpleNamespace(
        owner=owner,
        first=first,
        start=start,
        end=end,
        start_src=start_src,
        end_src=end_src,
        # 1 when the TAT used Date Decked and / or Date Released
        fallback=case((or_(start_src == "decked", end_src == "released"), 1), else_=0),
        days=_workdays(start, end),
        tat_ok=and_(start.isnot(None), end.isnot(None), end >= start),
    )


def _source_cond(pa: SimpleNamespace, source):
    """Keep only the apps whose TAT came from one source combination, given as
    "start:end", e.g. "decked:released". Anything else means no filter."""
    if not source or ":" not in source:
        return None
    start, end = source.split(":", 1)
    if start not in ("log", "decked") or end not in ("log", "released"):
        return None
    return and_(pa.start_src == start, pa.end_src == end)


def _handled(db: Session, pa: SimpleNamespace, user_id: int, *cols):
    """All applications handled by this person, open or closed."""
    return (
        db.query(*cols)
        .select_from(MainDB)
        .join(pa.owner, pa.owner.c.main_db_id == MainDB.DB_ID)
        .outerjoin(pa.first, pa.first.c.main_db_id == MainDB.DB_ID)
        .filter(pa.owner.c.user_id == user_id)
    )


# ── 1. Person search (autocomplete) ──────────────────────────
def search_evaluators(
    db: Session, q: str = "", limit: int = 15, role: str = "evaluator"
) -> list:
    """People who handled the role's step, by name or code, A-Z. An empty `q`
    lists everyone."""
    role = _role(role)
    q = (q or "").strip()
    person_ids = db.query(ApplicationLogs.user_id).filter(
        ApplicationLogs.application_step.ilike(ROLES[role]["pattern"]),
        ApplicationLogs.user_id.isnot(None),
    )
    query = db.query(User).filter(User.id.in_(person_ids))
    if q:
        pattern = (
            "%"
            + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        full = func.concat(User.first_name, " ", User.surname)
        query = query.filter(
            or_(
                full.ilike(pattern, escape="\\"),
                User.username.ilike(pattern, escape="\\"),
                User.alias.ilike(pattern, escape="\\"),
            )
        )
    rows = query.order_by(User.first_name, User.surname).limit(limit).all()
    return [
        {
            "user_id": u.id,
            "full_name": _full_name(u),
            "code": (u.alias or u.username or "").strip(),
            "position": u.position,
        }
        for u in rows
    ]


# ── 2. Monitoring for one person ─────────────────────────────
def get_evaluator_monitoring(
    db: Session,
    user_id: int,
    year: str = "All",
    month: str = "All",
    role: str = "evaluator",
    source: str = None,
):
    role = _role(role)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    pa = _parts(db, role, user_id)
    days, tat_ok = pa.days, pa.tat_ok
    # only the Companies and Drugs tables follow this filter
    src_cond = _source_cond(pa, source)
    src_filter = [src_cond] if src_cond is not None else []
    rec, rel = _dates()
    rec_ok = _valid(MainDB.DB_DATE_RECEIVED_CENT, rec)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)

    def handled(*cols):
        return _handled(db, pa, user_id, *cols)

    def closed(*cols):
        """Closed applications handled by this person."""
        return handled(*cols).filter(rel_ok)

    period = _period(rel, year, month)

    # ── Received / Released per year (or per month of a year) ──
    by_year = year in (None, "", "All")
    if by_year:
        rec_bucket, rel_bucket = func.year(rec), func.year(rel)
        rec_scope, rel_scope = [], []
    else:
        rec_bucket, rel_bucket = func.month(rec), func.month(rel)
        rec_scope = [func.year(rec) == int(year)]
        rel_scope = [func.year(rel) == int(year)]

    received = {
        r.b: int(r.n)
        for r in handled(rec_bucket.label("b"), func.count(MainDB.DB_ID).label("n"))
        .filter(rec_ok, *rec_scope)
        .group_by(rec_bucket)
        .all()
        if r.b is not None
    }
    released = {
        r.b: int(r.n)
        for r in closed(rel_bucket.label("b"), func.count(MainDB.DB_ID).label("n"))
        .filter(*rel_scope)
        .group_by(rel_bucket)
        .all()
        if r.b is not None
    }
    # What happened to the applications received in each period: the year they
    # were released in, or "not released" when there is no valid Date Released
    release_year = case((rel_ok, func.year(rel)), else_=None)
    split_rows = (
        handled(
            rec_bucket.label("b"),
            release_year.label("ry"),
            func.count(MainDB.DB_ID).label("n"),
        )
        .filter(rec_ok, *rec_scope)
        .group_by(rec_bucket, release_year)
        .all()
    )
    splits = {}
    for r in split_rows:
        if r.b is not None:
            splits.setdefault(r.b, []).append((r.ry, int(r.n)))

    # ...and the other way round: when the applications released in each
    # period were received ("no received date" when it is missing)
    receive_year = case((rec_ok, func.year(rec)), else_=None)
    rsplit_rows = (
        closed(
            rel_bucket.label("b"),
            receive_year.label("ry"),
            func.count(MainDB.DB_ID).label("n"),
        )
        .filter(*rel_scope)
        .group_by(rel_bucket, receive_year)
        .all()
    )
    rsplits = {}
    for r in rsplit_rows:
        if r.b is not None:
            rsplits.setdefault(r.b, []).append((r.ry, int(r.n)))

    def released_split(bucket):
        rows = rsplits.get(bucket, [])
        return {
            "received": [
                {"year": int(y), "count": n}
                for y, n in sorted((x for x in rows if x[0] is not None))
            ],
            "no_received_date": sum(n for y, n in rows if y is None),
        }

    def received_split(bucket):
        rows = splits.get(bucket, [])
        return {
            "released": [
                {"year": int(y), "count": n}
                for y, n in sorted((x for x in rows if x[0] is not None))
            ],
            "not_released": sum(n for y, n in rows if y is None),
        }

    if by_year:
        buckets = sorted(set(received) | set(released), reverse=True)
        periods = [
            {
                "key": int(b),
                "label": str(int(b)),
                "received": received.get(b, 0),
                "released": released.get(b, 0),
                "received_split": received_split(b),
                "released_split": released_split(b),
            }
            for b in buckets
        ]
    else:
        periods = [
            {
                "key": m,
                "label": MONTH_ABBR[m],
                "received": received.get(m, 0),
                "released": released.get(m, 0),
                "received_split": received_split(m),
                "released_split": released_split(m),
            }
            for m in range(1, 13)
        ]

    # ── Companies and drugs, ranked by average TAT ──
    # One row per name key. Spellings of the same name are merged; the most
    # common spelling is shown and all of them are listed.
    def ranked(key_expr, col):
        spelling = _spelling(col)
        rows = (
            closed(
                key_expr.label("k"),
                spelling.label("sp"),
                func.count(MainDB.DB_ID).label("n"),
                func.sum(days).label("tot"),
                func.min(days).label("fast"),
                func.max(days).label("slow"),
                func.sum(pa.fallback).label("fb"),
            )
            .filter(tat_ok, ~_empty(col), *period, *src_filter)
            .group_by(key_expr, spelling)
            .all()
        )
        groups = {}
        for r in rows:
            g = groups.setdefault(
                r.k,
                {"n": 0, "tot": 0.0, "fast": None, "slow": None, "fb": 0, "sp": []},
            )
            g["n"] += int(r.n)
            g["fb"] += int(r.fb or 0)
            g["tot"] += float(r.tot or 0)
            g["fast"] = r.fast if g["fast"] is None else min(g["fast"], r.fast)
            g["slow"] = r.slow if g["slow"] is None else max(g["slow"], r.slow)
            g["sp"].append({"name": r.sp, "count": int(r.n)})
        items = []
        for k, g in groups.items():
            g["sp"].sort(key=lambda x: (-x["count"], x["name"] or ""))
            items.append(
                {
                    "key": k,
                    "name": g["sp"][0]["name"],
                    "total_apps": g["n"],
                    "avg": g["tot"] / g["n"],
                    "fast": int(g["fast"]),
                    "slow": int(g["slow"]),
                    "fallback": g["fb"],
                    "spellings": g["sp"],
                }
            )
        items.sort(
            key=lambda x: (round(x["avg"], 1), -x["total_apps"], x["name"] or "")
        )
        # every row gets its own number; equal averages are ordered by more
        # applications first, then by name
        return [
            {
                "rank": rk,
                "key": x["key"],
                "name": x["name"],
                "total_apps": x["total_apps"],
                "avg_tat": _r1(x["avg"]),
                "fastest_tat": x["fast"],
                "slowest_tat": x["slow"],
                "fallback_apps": x["fallback"],
                "spellings": x["spellings"],
            }
            for rk, x in enumerate(items, start=1)
        ]

    companies = ranked(_ckey(), MainDB.DB_EST_LTO_COMP)
    drugs = ranked(_gkey(), MainDB.DB_PROD_GEN_NAME)

    # ── Summary and skipped applications ──
    closed_total = int(
        closed(func.count(MainDB.DB_ID)).filter(*period).scalar() or 0
    )
    counted = (
        closed(func.count(MainDB.DB_ID), func.avg(days))
        .filter(tat_ok, *period)
        .one()
    )
    counted_n = int(counted[0] or 0)
    no_company = int(
        closed(func.count(MainDB.DB_ID))
        .filter(tat_ok, _empty(MainDB.DB_EST_LTO_COMP), *period)
        .scalar()
        or 0
    )
    no_generic = int(
        closed(func.count(MainDB.DB_ID))
        .filter(tat_ok, _empty(MainDB.DB_PROD_GEN_NAME), *period)
        .scalar()
        or 0
    )

    source_rows = (
        closed(
            pa.start_src.label("ss"),
            pa.end_src.label("es"),
            func.count(MainDB.DB_ID).label("n"),
        )
        .filter(tat_ok, *period)
        .group_by(pa.start_src, pa.end_src)
        .all()
    )
    sources = sorted(
        (
            {"start": r.ss, "end": r.es, "count": int(r.n)}
            for r in source_rows
        ),
        key=lambda x: -x["count"],
    )

    reason = case(
        (pa.start.is_(None), R_NO_START),
        (pa.end.is_(None), R_NO_END),
        else_=R_BEFORE,
    )
    skipped_rows = (
        closed(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_EST_LTO_COMP,
            MainDB.DB_PROD_GEN_NAME,
            pa.start.label("tat_start"),
            pa.end.label("tat_end"),
            pa.start_src.label("start_src"),
            pa.end_src.label("end_src"),
            MainDB.DB_DATE_RELEASED,
            reason.label("reason"),
        )
        .filter(~tat_ok, *period)
        .order_by(rel.desc(), MainDB.DB_ID.desc())
        .limit(SKIPPED_LIMIT)
        .all()
    )
    reason_counts = {
        r.reason: int(r.n)
        for r in closed(reason.label("reason"), func.count(MainDB.DB_ID).label("n"))
        .filter(~tat_ok, *period)
        .group_by(reason)
        .all()
    }
    skipped_total = sum(reason_counts.values())

    def _d(v):
        return str(v)[:10] if v else None

    return {
        "role": role,
        "role_label": ROLES[role]["label"],
        "evaluator": {
            "user_id": user.id,
            "full_name": _full_name(user),
            "code": (user.alias or user.username or "").strip(),
            "position": user.position,
        },
        "filters": {
            "year": year,
            "month": month,
            "source": source if src_cond is not None else None,
        },
        "summary": {
            "closed_apps": closed_total,
            "counted_apps": counted_n,
            "skipped_apps": skipped_total,
            "avg_tat": _r1(counted[1]),
            "without_company": no_company,
            "without_generic": no_generic,
            "sources": sources,
        },
        "period_mode": "year" if by_year else "month",
        "periods": periods,
        "companies": companies,
        "drugs": drugs,
        "skipped": {
            "total": skipped_total,
            "by_reason": [
                {"reason": k, "count": v}
                for k, v in sorted(reason_counts.items(), key=lambda x: -x[1])
            ],
            "shown": len(skipped_rows),
            "rows": [
                {
                    "db_id": r.DB_ID,
                    "dtn": str(r.DB_DTN) if r.DB_DTN else None,
                    "company": (r.DB_EST_LTO_COMP or "").strip() or None,
                    "generic_name": (r.DB_PROD_GEN_NAME or "").strip() or None,
                    "tat_start": _d(r.tat_start),
                    "tat_end": _d(r.tat_end),
                    "tat_start_src": r.start_src,
                    "tat_end_src": r.end_src,
                    "date_released": _d(r.DB_DATE_RELEASED),
                    "reason": r.reason,
                }
                for r in skipped_rows
            ],
        },
        "formula": _formula(role),
    }


# ── 3. Applications behind one company or drug row ───────────
def get_evaluator_records(
    db: Session,
    user_id: int,
    kind: str,
    key: str,
    year: str = "All",
    month: str = "All",
    page: int = 1,
    page_size: int = 50,
    role: str = "evaluator",
    source: str = None,
):
    """The applications counted in one Company / Drug row of the monitoring.
    Same rules as get_evaluator_monitoring, so the total always matches the
    Total Apps number that was clicked."""
    role = _role(role)
    kind = "drug" if kind == "drug" else "company"
    col = MainDB.DB_PROD_GEN_NAME if kind == "drug" else MainDB.DB_EST_LTO_COMP
    key = (key or "").strip().upper()

    pa = _parts(db, role, user_id)
    days = pa.days
    rec, rel = _dates()
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)

    src_cond = _source_cond(pa, source)

    def scoped(*cols):
        return _handled(db, pa, user_id, *cols).filter(
            rel_ok,
            pa.tat_ok,
            ~_empty(col),
            _norm(col) == key,
            *_period(rel, year, month),
            *([src_cond] if src_cond is not None else []),
        )

    spelling = _spelling(col)
    sp_rows = (
        scoped(spelling.label("sp"), func.count(MainDB.DB_ID).label("n"))
        .group_by(spelling)
        .all()
    )
    spellings = sorted(
        ({"name": r.sp, "count": int(r.n)} for r in sp_rows),
        key=lambda x: (-x["count"], x["name"] or ""),
    )
    total = sum(x["count"] for x in spellings)
    avg = scoped(func.avg(days)).scalar()

    rows = (
        scoped(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_EST_LTO_COMP,
            MainDB.DB_PROD_GEN_NAME,
            MainDB.DB_PROD_BR_NAME,
            MainDB.DB_TYPE_DOC_RELEASED,
            MainDB.DB_APP_STATUS,
            MainDB.DB_DATE_RECEIVED_CENT,
            pa.start.label("tat_start"),
            pa.end.label("tat_end"),
            pa.start_src.label("start_src"),
            pa.end_src.label("end_src"),
            MainDB.DB_DATE_RELEASED,
            days.label("tat"),
        )
        .order_by(rel.desc(), MainDB.DB_ID.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def _d(v):
        return str(v)[:10] if v else None

    def _t(v):
        return (v or "").strip() or None

    return {
        "role": role,
        "role_label": ROLES[role]["label"],
        "kind": kind,
        "key": key,
        "name": spellings[0]["name"] if spellings else None,
        "total": total,
        "avg_tat": _r1(avg),
        "spellings": spellings,
        "page": page,
        "page_size": page_size,
        "rows": [
            {
                "db_id": r.DB_ID,
                "dtn": str(r.DB_DTN) if r.DB_DTN else None,
                "company": _t(r.DB_EST_LTO_COMP),
                "generic_name": _t(r.DB_PROD_GEN_NAME),
                "brand_name": _t(r.DB_PROD_BR_NAME),
                "doc_type": _t(r.DB_TYPE_DOC_RELEASED),
                "status": _t(r.DB_APP_STATUS),
                "date_received": _d(r.DB_DATE_RECEIVED_CENT),
                "tat_start": _d(r.tat_start),
                "tat_end": _d(r.tat_end),
                "tat_start_src": r.start_src,
                "tat_end_src": r.end_src,
                "date_released": _d(r.DB_DATE_RELEASED),
                "tat": int(r.tat) if r.tat is not None else None,
            }
            for r in rows
        ],
    }


# ── 4. Applications behind one Received / Released number ────
def get_period_records(
    db: Session,
    user_id: int,
    side: str,
    bucket: int,
    year: str = "All",
    month: str = "All",
    other_year: int = None,
    rest: bool = False,
    page: int = 1,
    page_size: int = 50,
    role: str = "evaluator",
):
    """The applications counted in one Received or Released number of the
    Received / Released card (the whole number, or one part of its split).

    side="received": handled by the person and received in the period (open or
                     closed). other_year = released in that year, rest = not
                     released yet.
    side="released": closed and released in the period. other_year = received
                     in that year, rest = no received date.
    bucket is the year, or the month when a year is selected.
    """
    role = _role(role)
    side = "released" if side == "released" else "received"
    pa = _parts(db, role, user_id)
    days, tat_ok = pa.days, pa.tat_ok
    rec, rel = _dates()
    rec_ok = _valid(MainDB.DB_DATE_RECEIVED_CENT, rec)
    rel_ok = _valid(MainDB.DB_DATE_RELEASED, rel)

    by_year = year in (None, "", "All")

    def in_bucket(d):
        if by_year:
            return [func.year(d) == bucket]
        return [func.year(d) == int(year), func.month(d) == bucket]

    if side == "received":
        conds = [rec_ok, *in_bucket(rec)]
        if rest:
            conds.append(~rel_ok)
        elif other_year is not None:
            conds += [rel_ok, func.year(rel) == other_year]
        order = rec
    else:
        conds = [rel_ok, *in_bucket(rel)]
        if rest:
            conds.append(~rec_ok)
        elif other_year is not None:
            conds += [rec_ok, func.year(rec) == other_year]
        order = rel

    def scoped(*cols):
        return _handled(db, pa, user_id, *cols).filter(*conds)

    total = int(scoped(func.count(MainDB.DB_ID)).scalar() or 0)
    avg = scoped(func.avg(days)).filter(tat_ok).scalar()

    rows = (
        scoped(
            MainDB.DB_ID,
            MainDB.DB_DTN,
            MainDB.DB_EST_LTO_COMP,
            MainDB.DB_PROD_GEN_NAME,
            MainDB.DB_PROD_BR_NAME,
            MainDB.DB_TYPE_DOC_RELEASED,
            MainDB.DB_APP_STATUS,
            MainDB.DB_DATE_RECEIVED_CENT,
            pa.start.label("tat_start"),
            pa.end.label("tat_end"),
            pa.start_src.label("start_src"),
            pa.end_src.label("end_src"),
            MainDB.DB_DATE_RELEASED,
            case((tat_ok, days), else_=None).label("tat"),
        )
        .order_by(order.desc(), MainDB.DB_ID.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    label = str(bucket) if by_year else f"{MONTH_ABBR[bucket]} {year}"
    if side == "received":
        title = f"Received in {label}"
        if rest:
            title += " · not released yet"
        elif other_year is not None:
            title += f" · released in {other_year}"
    else:
        title = f"Released in {label}"
        if rest:
            title += " · no received date"
        elif other_year is not None:
            title += f" · received in {other_year}"

    def _d(v):
        return str(v)[:10] if v else None

    def _t(v):
        return (v or "").strip() or None

    return {
        "role": role,
        "role_label": ROLES[role]["label"],
        "kind": "period",
        "side": side,
        "key": None,
        "name": title,
        "total": total,
        "avg_tat": _r1(avg),
        "spellings": [],
        "page": page,
        "page_size": page_size,
        "rows": [
            {
                "db_id": r.DB_ID,
                "dtn": str(r.DB_DTN) if r.DB_DTN else None,
                "company": _t(r.DB_EST_LTO_COMP),
                "generic_name": _t(r.DB_PROD_GEN_NAME),
                "brand_name": _t(r.DB_PROD_BR_NAME),
                "doc_type": _t(r.DB_TYPE_DOC_RELEASED),
                "status": _t(r.DB_APP_STATUS),
                "date_received": _d(r.DB_DATE_RECEIVED_CENT),
                "tat_start": _d(r.tat_start),
                "tat_end": _d(r.tat_end),
                "tat_start_src": r.start_src,
                "tat_end_src": r.end_src,
                "date_released": _d(r.DB_DATE_RELEASED),
                "tat": int(r.tat) if r.tat is not None else None,
            }
            for r in rows
        ],
    }
