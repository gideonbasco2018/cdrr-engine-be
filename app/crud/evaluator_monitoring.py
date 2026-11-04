# app/crud/evaluator_monitoring.py
#
# User Insights: for one person, in one or more workflow roles (see ROLES),
# how the closed applications they handled did per company and per drug
# (ranked by average turnaround time), and how many were received / released
# per year or month.
#
# Two data sources, chosen with `sources` ("cpr", "fgmp" or "cpr,fgmp"):
#   cpr  : main_db + application_logs      (steps Quality Evaluation / Checking ...)
#   fgmp : gmp_record + gmp_application_logs (steps Evaluator / Checker ...)
# Every query is written once, against a source description (see _source).
# When both are chosen each source is computed on its own and the results are
# merged, so the totals are the sums of the two.
#
# Reuses the rules already used by the other analytics views:
#   - company key      : letters and digits only (see _norm)
#   - working days     : Mon-Fri between two dates             (Fastest Processing)
#   - valid date       : readable, year 2000-2100              (Company Monitoring)
#
# Who handled an application: every person who has a step of the role on it
# that was NOT reassigned away from them.
#   - reassigned from A to B   -> counts for B only (A's step is marked)
#   - reassigned to this person -> counts for this person (their step is not marked)
#   - rerouted to someone else  -> still counts for the person who had it
# For one person the "own step" is their latest such step on the application.
# Closed application = has a valid Date Released.
#
# TAT = working days from a START to a FINISH, each with a fallback:
#   START  1st: the start of the first step of the role that has a date in the
#               application log
#          2nd: CPR: the Date Decked of the application (DB_DATE_DECK)
#               FGMP: the finish of the Decking step in the log
#   FINISH 1st: the finish of the person's own step in the application log
#          2nd: the Date Released of the application
# Each application says where its start and its finish came from ("log" or
# "decked" / "released"), so a reader can tell a log TAT from a fallback one.
# Only Evaluator and Checker have the 2nd choices; every other role uses the
# dates of its own log step only (no fallback).
# Applications with no usable start or finish are skipped, with the reason.
from types import SimpleNamespace

from sqlalchemy import and_, case, func, null, or_
from sqlalchemy.orm import Session, aliased

from app.models.main_db import MainDB
from app.models.application_logs import ApplicationLogs
from app.models.gmp_record import GMPRecord, GMPApplicationLogs
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

# The workflow steps a person can be looked at for, in workflow order.
# fallback: True = a missing log date may be filled from the application
# (decked date / Date Released). Only Evaluator and Checker have it; every
# other role uses the dates of its own log step only.
ROLES = {
    "decker": {"label": "Decker", "fallback": False},
    "evaluator": {"label": "Evaluator", "fallback": True},
    "checker": {"label": "Checker", "fallback": True},
    "supervisor": {"label": "Supervisor", "fallback": False},
    "lrd_chief": {"label": "LRD Chief Admin", "fallback": False},
    "qa_admin": {"label": "QA Admin", "fallback": False},
    "od_receiving": {"label": "OD Receiving", "fallback": False},
    "od_releasing": {"label": "OD Releasing", "fallback": False},
}
LOG_ONLY_NOTE = (
    "The decked-date and Date Released fallbacks are used for the Evaluator "
    "and Checker only; the other roles use the dates of their own log step "
    "only."
)

R_NO_START = "No start date (not in the application log, no usable decked date)"
R_NO_END = "No finish date (not in the application log, no valid Date Released)"
R_NO_START_LOG = "No start date (not in the application log)"
R_NO_END_LOG = "No finish date (not in the application log)"
R_BEFORE = "Finished before it started"

NO_DOC_TYPE = "No document type"


# ── The two sources ──────────────────────────────────────────
def _in_range(d):
    return and_(d.isnot(None), func.year(d) >= 2000, func.year(d) <= 2100)


def _cpr_source():
    return SimpleNamespace(
        key="cpr",
        label="CPR",
        MODEL=MainDB,
        ID=MainDB.DB_ID,
        DTN=MainDB.DB_DTN,
        COMPANY=MainDB.DB_EST_LTO_COMP,
        DRUG=MainDB.DB_PROD_GEN_NAME,
        BRAND=MainDB.DB_PROD_BR_NAME,
        DOC=MainDB.DB_TYPE_DOC_RELEASED,
        STATUS=MainDB.DB_APP_STATUS,
        REC_RAW=MainDB.DB_DATE_RECEIVED_CENT,
        REL_RAW=MainDB.DB_DATE_RELEASED,
        LOG=ApplicationLogs,
        LOG_FK=ApplicationLogs.main_db_id,
        base_filter=[],
        steps={
            "decker": "Decking",
            "evaluator": "%quality evaluation%",
            "checker": "%checking%",
            "supervisor": "Supervisor",
            "lrd_chief": "LRD Chief%",
            "qa_admin": "QA Admin",
            "od_receiving": "OD-Receiving",
            "od_releasing": "OD-Releasing",
        },
        step_names={
            "decker": "Decking",
            "evaluator": "Quality Evaluation",
            "checker": "Checking",
            "supervisor": "Supervisor",
            "lrd_chief": "LRD Chief Admin",
            "qa_admin": "QA Admin",
            "od_receiving": "OD-Receiving",
            "od_releasing": "OD-Releasing",
        },
        decking_pattern=None,  # the fallback is a column of the application
        dates=_dates,
        rec_ok=lambda d: _valid(MainDB.DB_DATE_RECEIVED_CENT, d),
        rel_ok=lambda d: _valid(MainDB.DB_DATE_RELEASED, d),
    )


def _fgmp_source():
    return SimpleNamespace(
        key="fgmp",
        label="FGMP",
        MODEL=GMPRecord,
        ID=GMPRecord.GMP_ID,
        DTN=GMPRecord.GMP_DTN,
        COMPANY=GMPRecord.GMP_LTO_COMPANY,
        DRUG=GMPRecord.GMP_PRODUCT_LINE,  # FGMP has no drug: the product line
        BRAND=null(),
        DOC=GMPRecord.GMP_TYPE_OF_ISSUANCE,
        STATUS=GMPRecord.GMP_APP_STATUS,
        REC_RAW=GMPRecord.GMP_DATE_RECEIVED,
        REL_RAW=GMPRecord.GMP_RELEASED_DATE,
        LOG=GMPApplicationLogs,
        LOG_FK=GMPApplicationLogs.gmp_record_id,
        base_filter=[
            or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted")
        ],
        steps={
            "decker": "Decking",
            "evaluator": "Evaluator",
            "checker": "Checker",
            "supervisor": "Supervisor",
            "lrd_chief": "LRD Chief%",
            "qa_admin": "QA Admin",
            "od_receiving": "OD Receiving",
            "od_releasing": "OD Releasing",
        },
        step_names={
            "decker": "Decking",
            "evaluator": "Evaluator",
            "checker": "Checker",
            "supervisor": "Supervisor",
            "lrd_chief": "LRD Chief Admin",
            "qa_admin": "QA Admin",
            "od_receiving": "OD Receiving",
            "od_releasing": "OD Releasing",
        },
        decking_pattern="Decking",  # the fallback is the finish of this log step
        dates=lambda: (GMPRecord.GMP_DATE_RECEIVED, GMPRecord.GMP_RELEASED_DATE),
        rec_ok=lambda d: _in_range(d),
        rel_ok=lambda d: _in_range(d),
    )


SOURCES = {"cpr": _cpr_source, "fgmp": _fgmp_source}


def _source_list(sources) -> list:
    """The chosen sources as source objects, in a fixed order (cpr, fgmp).
    Accepts "cpr,fgmp", a list, or nothing (= cpr only)."""
    if isinstance(sources, str):
        sources = [s.strip().lower() for s in sources.split(",")]
    chosen = [k for k in SOURCES if k in (sources or [])] or ["cpr"]
    return [SOURCES[k]() for k in chosen]


def _role(role: str) -> str:
    return role if role in ROLES else "evaluator"


def _role_list(role) -> list:
    """The chosen roles ("evaluator", "checker" or "evaluator,checker") in a
    fixed order; evaluator alone when nothing valid is given."""
    if isinstance(role, str):
        role = [r.strip().lower() for r in role.split(",")]
    return [r for r in ROLES if r in (role or [])] or ["evaluator"]


def _units(sources, role) -> list:
    """Every (source, role) pair to read. Each is computed on its own and the
    results are added up, so an application the person handled in both roles
    counts once for each role (with its own TAT)."""
    return [(S, r) for S in _source_list(sources) for r in _role_list(role)]


def _role_label(roles) -> str:
    if len(roles) == len(ROLES):
        return "All Roles"
    return " + ".join(ROLES[r]["label"] for r in roles)


def _formula(roles, keys: list) -> dict:
    if isinstance(roles, str):
        roles = [roles]
    srcs = [SOURCES[k]() for k in keys]
    many = len(roles) > 2  # too many step names for one sentence
    if many:
        who = "person"
        step = "chosen-role"
        steps_read = " Steps read: " + "; ".join(
            f"{s.label}: " + ", ".join(s.step_names[r] for r in roles) for s in srcs
        ) + "."
    else:
        who = " or ".join(ROLES[r]["label"].lower() for r in roles)
        step = " / ".join(
            s.step_names[r] + (f" ({s.label})" if len(srcs) > 1 else "")
            for r in roles
            for s in srcs
        )
        steps_read = ""
    has_fgmp = "fgmp" in keys
    has_cpr = "cpr" in keys
    any_fb = any(ROLES[r]["fallback"] for r in roles)  # some role has fallbacks
    all_fb = all(ROLES[r]["fallback"] for r in roles)
    fallback_start = (
        "the Date Decked of the application"
        if has_cpr and not has_fgmp
        else "the finish of the Decking step (FGMP)"
        if has_fgmp and not has_cpr
        else "the Date Decked of the application (CPR) or the finish of the "
        "Decking step (FGMP)"
    )
    fallback_dates = (
        "Date Decked and the Date Released"
        if not has_fgmp
        else "decked date (the Decking step for FGMP) and the Date Released"
    )
    if any_fb:
        tat = (
            f"TAT = working days (Monday to Friday) from a start to a finish. "
            f"Start = the start of the first {step} step that has a date "
            f"in the application log; if there is none, {fallback_start}. "
            f"Finish = the finish of the {who}'s own {step} "
            f"step in the application log; if there is none, the Date "
            f"Released. Every application shows where its start and its "
            f"finish came from. Same day = 0. Holidays are not deducted."
        ) + ("" if all_fb else " " + LOG_ONLY_NOTE)
    else:
        tat = (
            f"TAT = working days (Monday to Friday) from a start to a finish. "
            f"Start = the start of the first {step} step that has a date "
            f"in the application log. "
            f"Finish = the finish of the {who}'s own {step} "
            f"step in the application log. An application with no start or "
            f"no finish date in the log is skipped and listed with the "
            f"reason. Same day = 0. Holidays are not deducted."
        )
    out = {
        "closed": "Closed application = an application with a valid Date Released.",
        "tat": tat,
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
            f"{_role_label(roles)} = the user of a {step} step on the "
            f"application that was not reassigned away from them. An app "
            f"reassigned from one person to another counts for the new person "
            f"only; an app rerouted to someone else still counts for the "
            f"person who had it."
            + steps_read
            + (
                " When several roles are chosen, an application the person "
                "handled in more than one role counts once for each "
                "role, each with its own TAT."
                if len(roles) > 1
                else ""
            )
            + (
                f" Application logs from before April 2026 "
                f"mostly have no dates, so those applications use the "
                f"{fallback_dates} instead (and say so)."
                if all_fb
                else " Application logs from before April 2026 mostly have "
                "no dates. Evaluator and Checker then use the "
                f"{fallback_dates} instead (and say so); the other roles "
                "have no fallback, so those applications are skipped and "
                "listed with the reason."
                if any_fb
                else " Application logs from before April 2026 mostly have "
                "no dates, and these roles have no fallback, so those "
                "applications are skipped and listed with the reason."
            )
        ),
        "received": (
            f"Received counts all applications handled by the {who}, open or "
            f"closed. Released counts the applications with a valid Date "
            f"Released."
        ),
    }
    if has_fgmp:
        fg_steps = (
            "Evaluator and Checker"
            if set(roles) <= {"evaluator", "checker"}
            else " / ".join(SOURCES["fgmp"]().step_names[r] for r in roles)
        )
        out["fgmp"] = (
            "FGMP applications come from the FGMP records and their log (steps "
            f"{fg_steps}). FGMP has no drug, so the Drugs table "
            "ranks the Product Line instead."
        )
    return out


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


def _d(v):
    return str(v)[:10] if v else None


def _t(v):
    return (v or "").strip() or None


def _parts(db: Session, S, role: str, user_id: int) -> SimpleNamespace:
    """Sub-queries and expressions that read one role's steps from the log.
    Only the applications this person ever had a step on are read, which keeps
    the queries fast."""
    L = S.LOG
    fk = S.LOG_FK
    pattern = S.steps[role]
    mine = db.query(fk).filter(L.user_id == user_id, L.application_step.ilike(pattern))

    # this person's own step on the app: their latest step of the role that
    # was not reassigned away from them (see the rules at the top)
    rn = func.row_number().over(
        partition_by=fk,
        order_by=(L.del_index.desc(), L.id.desc()),
    )
    ranked_rows = (
        db.query(
            fk.label("rid"),
            L.user_id.label("user_id"),
            L.del_index.label("del_index"),
            L.accomplished_date.label("done"),
            rn.label("rn"),
        )
        .filter(
            L.application_step.ilike(pattern),
            L.user_id == user_id,
            L.reassigned_at.is_(None),
            L.reassigned_by_user_id.is_(None),
            fk.in_(mine),
        )
        .subquery()
    )
    owner = (
        db.query(
            ranked_rows.c.rid,
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
            fk.label("rid"),
            func.min(L.start_date).label("first_start"),
            func.min(L.del_index).label("first_idx"),
        )
        .filter(L.application_step.ilike(pattern), fk.in_(mine))
        .group_by(fk)
        .subquery()
    )
    # fallbacks that come from the application itself
    rec, rel = S.dates()
    rel_ok = S.rel_ok(rel)
    deck_sub = None
    use_fallback = ROLES[role]["fallback"]
    if not use_fallback:
        deck = deck_ok = None  # log dates only: nothing to fall back on
    elif S.decking_pattern is None:
        deck = func.str_to_date(func.left(MainDB.DB_DATE_DECK, 10), "%Y-%m-%d")
        deck_ok = _valid(MainDB.DB_DATE_DECK, deck)
    else:
        # FGMP: the finish of the Decking step is the decked date
        deck_sub = (
            db.query(
                fk.label("rid"),
                func.max(L.accomplished_date).label("deck"),
            )
            .filter(L.application_step.ilike(S.decking_pattern), fk.in_(mine))
            .group_by(fk)
            .subquery()
        )
        deck = deck_sub.c.deck
        deck_ok = deck.isnot(None)

    # START: first dated step of the role in the log, else the decked date
    # FINISH: the person's own step in the log, else Date Released
    if use_fallback:
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
    else:
        start = first.c.first_start
        end = owner.c.done
        start_src = case((start.isnot(None), "log"), else_=None)
        end_src = case((end.isnot(None), "log"), else_=None)
    return SimpleNamespace(
        S=S,
        owner=owner,
        first=first,
        deck_sub=deck_sub,
        start=start,
        end=end,
        start_src=start_src,
        end_src=end_src,
        # 1 when the TAT used the decked date and / or Date Released
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
    S = pa.S
    q = (
        db.query(*cols)
        .select_from(S.MODEL)
        .join(pa.owner, pa.owner.c.rid == S.ID)
        .outerjoin(pa.first, pa.first.c.rid == S.ID)
    )
    if pa.deck_sub is not None:
        q = q.outerjoin(pa.deck_sub, pa.deck_sub.c.rid == S.ID)
    return q.filter(pa.owner.c.user_id == user_id, *S.base_filter)


# ── Merging the results of several sources ───────────────────
def _merge_items(lists, key_fn=lambda x: x["key"]):
    """Add up the counts of items with the same key, in several lists."""
    out = {}
    for lst in lists:
        for it in lst:
            k = key_fn(it)
            if k in out:
                out[k]["count"] += it["count"]
            else:
                out[k] = dict(it)
    return out


def _rank_items(items: dict) -> list:
    """Turn merged company / drug groups into the ranked rows of the API."""
    rows = []
    for k, g in items.items():
        g["sp"].sort(key=lambda x: (-x["count"], x["name"] or ""))
        rows.append(
            {
                "key": k,
                "name": g["sp"][0]["name"],
                "total_apps": g["n"],
                "avg": g["tot"] / g["n"],
                "fast": int(g["fast"]),
                "slow": int(g["slow"]),
                "fallback": g["fb"],
                "spellings": g["sp"],
                "by_source": g["by_source"],
            }
        )
    rows.sort(key=lambda x: (round(x["avg"], 1), -x["total_apps"], x["name"] or ""))
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
            "by_source": x["by_source"],
        }
        for rk, x in enumerate(rows, start=1)
    ]


def _merge_ranked(parts_groups):
    """parts_groups: one dict per source of key -> group (see _monitoring_one)."""
    merged = {}
    for src_key, groups in parts_groups:
        for k, g in groups.items():
            m = merged.setdefault(
                k,
                {"n": 0, "tot": 0.0, "fast": None, "slow": None, "fb": 0, "sp": {}, "by": {}},
            )
            m["n"] += g["n"]
            m["tot"] += g["tot"]
            m["fb"] += g["fb"]
            m["fast"] = g["fast"] if m["fast"] is None else min(m["fast"], g["fast"])
            m["slow"] = g["slow"] if m["slow"] is None else max(m["slow"], g["slow"])
            m["by"][src_key] = m["by"].get(src_key, 0) + g["n"]
            for sp in g["sp"]:
                m["sp"][sp["name"]] = m["sp"].get(sp["name"], 0) + sp["count"]
    for m in merged.values():
        m["sp"] = [{"name": n, "count": c} for n, c in m["sp"].items()]
        m["by_source"] = m.pop("by")
    return merged


# ── 1. Person search (autocomplete) ──────────────────────────
def search_evaluators(
    db: Session,
    q: str = "",
    limit: int = 15,
    role="evaluator",
    sources="cpr",
) -> list:
    """People who handled a step of any chosen role in any chosen source, by
    name or code, A-Z. An empty `q` lists everyone. Each person says in which
    sources (of all) they have worked, so the page can tag them."""
    roles = _role_list(role)
    q = (q or "").strip()
    units = _units(sources, roles)

    def people(S, r):
        return db.query(S.LOG.user_id).filter(
            S.LOG.application_step.ilike(S.steps[r]), S.LOG.user_id.isnot(None)
        )

    query = db.query(User).filter(or_(*[User.id.in_(people(S, r)) for S, r in units]))
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
    users = query.order_by(User.first_name, User.surname).limit(limit).all()

    ids = [u.id for u in users]
    where = {}
    if ids:
        for key, make in SOURCES.items():
            S = make()
            rows = (
                db.query(S.LOG.user_id)
                .filter(
                    or_(*[S.LOG.application_step.ilike(S.steps[r]) for r in roles]),
                    S.LOG.user_id.in_(ids),
                )
                .distinct()
                .all()
            )
            for (uid,) in rows:
                where.setdefault(uid, []).append(key)
    return [
        {
            "user_id": u.id,
            "full_name": _full_name(u),
            "code": (u.alias or u.username or "").strip(),
            "position": u.position,
            "sources": where.get(u.id, []),
        }
        for u in users
    ]


# ── Years for the Year filter ────────────────────────────────
def get_evaluator_years(
    db: Session, user_id: int, role="evaluator", sources="cpr"
) -> list:
    """The years in which this person received or released an application, in
    the chosen sources and roles, newest last (like the other year lists)."""
    years = set()
    for S, role in _units(sources, role):
        pa = _parts(db, S, role, user_id)
        rec, rel = S.dates()
        for d, ok in ((rec, S.rec_ok(rec)), (rel, S.rel_ok(rel))):
            rows = (
                _handled(db, pa, user_id, func.year(d).label("y"))
                .filter(ok)
                .distinct()
                .all()
            )
            years.update(int(r.y) for r in rows if r.y)
    return [str(y) for y in sorted(years)]


# ── 2. Monitoring for one person ─────────────────────────────
def _monitoring_one(db, S, user_id, role, year, month, source, split):
    """Everything of the monitoring for ONE source, in a form that can be
    merged with the other source (counts and sums, not averages)."""
    pa = _parts(db, S, role, user_id)
    days, tat_ok = pa.days, pa.tat_ok
    # only the Companies and Drugs tables follow this filter
    src_cond = _source_cond(pa, source)
    src_filter = [src_cond] if src_cond is not None else []
    rec, rel = S.dates()
    rec_ok = S.rec_ok(rec)
    rel_ok = S.rel_ok(rel)

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
        for r in handled(rec_bucket.label("b"), func.count(S.ID).label("n"))
        .filter(rec_ok, *rec_scope)
        .group_by(rec_bucket)
        .all()
        if r.b is not None
    }
    released = {
        r.b: int(r.n)
        for r in closed(rel_bucket.label("b"), func.count(S.ID).label("n"))
        .filter(*rel_scope)
        .group_by(rel_bucket)
        .all()
        if r.b is not None
    }
    # What happened to the applications received in each period: the year (or
    # month) they were released in, or "not released" when there is no valid
    # Date Released
    month_split = split == "month"

    def split_key(d, ok):
        if month_split:  # 202603 = March 2026
            return case((ok, func.year(d) * 100 + func.month(d)), else_=None)
        return case((ok, func.year(d)), else_=None)

    def split_item(ym, count):
        ym = int(ym)
        if month_split:
            y, m = divmod(ym, 100)
            return {
                "key": ym,
                "year": y,
                "month": m,
                "label": f"{MONTH_ABBR[m]} {y}",
                "count": count,
            }
        return {"key": ym, "year": ym, "month": None, "label": str(ym), "count": count}

    release_year = split_key(rel, rel_ok)
    splits = {}
    for r in (
        handled(
            rec_bucket.label("b"), release_year.label("ry"), func.count(S.ID).label("n")
        )
        .filter(rec_ok, *rec_scope)
        .group_by(rec_bucket, release_year)
        .all()
    ):
        if r.b is not None:
            splits.setdefault(r.b, []).append((r.ry, int(r.n)))

    # ...and the other way round: when the applications released in each
    # period were received ("no received date" when it is missing)
    receive_year = split_key(rec, rec_ok)
    rsplits = {}
    for r in (
        closed(
            rel_bucket.label("b"), receive_year.label("ry"), func.count(S.ID).label("n")
        )
        .filter(*rel_scope)
        .group_by(rel_bucket, receive_year)
        .all()
    ):
        if r.b is not None:
            rsplits.setdefault(r.b, []).append((r.ry, int(r.n)))

    def released_split(bucket):
        rows = rsplits.get(bucket, [])
        return {
            "received": [
                split_item(y, n) for y, n in sorted(x for x in rows if x[0] is not None)
            ],
            "no_received_date": sum(n for y, n in rows if y is None),
        }

    def received_split(bucket):
        rows = splits.get(bucket, [])
        return {
            "released": [
                split_item(y, n) for y, n in sorted(x for x in rows if x[0] is not None)
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

    # ── Companies and drugs: one group per name key ──
    # Spellings of the same name are merged here; the most common spelling is
    # shown and all of them are listed.
    def groups(key_expr, col):
        spelling = _spelling(col)
        rows = (
            closed(
                key_expr.label("k"),
                spelling.label("sp"),
                func.count(S.ID).label("n"),
                func.sum(days).label("tot"),
                func.min(days).label("fast"),
                func.max(days).label("slow"),
                func.sum(pa.fallback).label("fb"),
            )
            .filter(tat_ok, ~_empty(col), *period, *src_filter)
            .group_by(key_expr, spelling)
            .all()
        )
        out = {}
        for r in rows:
            g = out.setdefault(
                r.k, {"n": 0, "tot": 0.0, "fast": None, "slow": None, "fb": 0, "sp": []}
            )
            g["n"] += int(r.n)
            g["fb"] += int(r.fb or 0)
            g["tot"] += float(r.tot or 0)
            g["fast"] = r.fast if g["fast"] is None else min(g["fast"], r.fast)
            g["slow"] = r.slow if g["slow"] is None else max(g["slow"], r.slow)
            g["sp"].append({"name": r.sp, "count": int(r.n)})
        return out

    company_groups = groups(_norm(S.COMPANY), S.COMPANY)
    drug_groups = groups(_norm(S.DRUG), S.DRUG)

    # ── Summary and skipped applications ──
    closed_total = int(closed(func.count(S.ID)).filter(*period).scalar() or 0)
    counted = (
        closed(func.count(S.ID), func.sum(days)).filter(tat_ok, *period).one()
    )
    no_company = int(
        closed(func.count(S.ID))
        .filter(tat_ok, _empty(S.COMPANY), *period)
        .scalar()
        or 0
    )
    no_generic = int(
        closed(func.count(S.ID)).filter(tat_ok, _empty(S.DRUG), *period).scalar() or 0
    )
    source_rows = (
        closed(
            pa.start_src.label("ss"),
            pa.end_src.label("es"),
            func.count(S.ID).label("n"),
        )
        .filter(tat_ok, *period)
        .group_by(pa.start_src, pa.end_src)
        .all()
    )

    fb = ROLES[role]["fallback"]
    reason = case(
        (pa.start.is_(None), R_NO_START if fb else R_NO_START_LOG),
        (pa.end.is_(None), R_NO_END if fb else R_NO_END_LOG),
        else_=R_BEFORE,
    )
    skipped_rows = (
        closed(
            S.ID.label("rid"),
            S.DTN.label("dtn"),
            S.COMPANY.label("company"),
            S.DRUG.label("drug"),
            pa.start.label("tat_start"),
            pa.end.label("tat_end"),
            pa.start_src.label("start_src"),
            pa.end_src.label("end_src"),
            S.REL_RAW.label("rel_raw"),
            reason.label("reason"),
        )
        .filter(~tat_ok, *period)
        .order_by(rel.desc(), S.ID.desc())
        .limit(SKIPPED_LIMIT)
        .all()
    )
    reason_counts = {
        r.reason: int(r.n)
        for r in closed(reason.label("reason"), func.count(S.ID).label("n"))
        .filter(~tat_ok, *period)
        .group_by(reason)
        .all()
    }

    return {
        "key": S.key,
        "role": role,
        "by_year": by_year,
        "periods": periods,
        "company_groups": company_groups,
        "drug_groups": drug_groups,
        "closed_total": closed_total,
        "counted_n": int(counted[0] or 0),
        "tat_sum": float(counted[1] or 0),
        "no_company": no_company,
        "no_generic": no_generic,
        "tat_sources": [
            {"start": r.ss, "end": r.es, "count": int(r.n)} for r in source_rows
        ],
        "reason_counts": reason_counts,
        "skipped_rows": [
            {
                "source": S.key,
                "role": role,
                "db_id": r.rid,
                "dtn": str(r.dtn) if r.dtn else None,
                "company": _t(r.company),
                "generic_name": _t(r.drug),
                "tat_start": _d(r.tat_start),
                "tat_end": _d(r.tat_end),
                "tat_start_src": r.start_src,
                "tat_end_src": r.end_src,
                "date_released": _d(r.rel_raw),
                "reason": r.reason,
            }
            for r in skipped_rows
        ],
        "src_cond_used": src_cond is not None,
    }


def _merge_periods(parts, by_year):
    merged = {}
    for part in parts:
        for p in part["periods"]:
            m = merged.setdefault(
                p["key"],
                {
                    "key": p["key"],
                    "label": p["label"],
                    "received": 0,
                    "released": 0,
                    "rs": [],
                    "rn": 0,
                    "ls": [],
                    "ln": 0,
                },
            )
            m["received"] += p["received"]
            m["released"] += p["released"]
            m["rs"].append(p["received_split"]["released"])
            m["rn"] += p["received_split"]["not_released"]
            m["ls"].append(p["released_split"]["received"])
            m["ln"] += p["released_split"]["no_received_date"]
    out = []
    for k, m in merged.items():
        out.append(
            {
                "key": m["key"],
                "label": m["label"],
                "received": m["received"],
                "released": m["released"],
                "received_split": {
                    "released": sorted(
                        _merge_items(m["rs"]).values(), key=lambda x: x["key"]
                    ),
                    "not_released": m["rn"],
                },
                "released_split": {
                    "received": sorted(
                        _merge_items(m["ls"]).values(), key=lambda x: x["key"]
                    ),
                    "no_received_date": m["ln"],
                },
            }
        )
    out.sort(key=lambda p: p["key"])  # oldest year first, newest last
    return out


def get_evaluator_monitoring(
    db: Session,
    user_id: int,
    year: str = "All",
    month: str = "All",
    role="evaluator",
    source: str = None,
    split: str = "year",
    sources="cpr",
):
    """split = "year" (the year of the other side) or "month" (its year and
    month): it only changes how the Received / Released splits are cut.
    sources = which data to use ("cpr", "fgmp" or "cpr,fgmp")."""
    roles = _role_list(role)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    units = _units(sources, roles)
    keys = list(dict.fromkeys(S.key for S, _ in units))
    parts = [
        _monitoring_one(db, S, user_id, r, year, month, source, split)
        for S, r in units
    ]
    by_year = parts[0]["by_year"]

    periods = (
        parts[0]["periods"] if len(parts) == 1 else _merge_periods(parts, by_year)
    )
    companies = _rank_items(
        _merge_ranked([(p["key"], p["company_groups"]) for p in parts])
    )
    drugs = _rank_items(_merge_ranked([(p["key"], p["drug_groups"]) for p in parts]))

    counted_n = sum(p["counted_n"] for p in parts)
    tat_sum = sum(p["tat_sum"] for p in parts)
    tat_sources = {}
    for p in parts:
        for s in p["tat_sources"]:
            k = (s["start"], s["end"])
            tat_sources[k] = tat_sources.get(k, 0) + s["count"]
    reasons = {}
    for p in parts:
        for k, v in p["reason_counts"].items():
            reasons[k] = reasons.get(k, 0) + v
    skipped_rows = [r for p in parts for r in p["skipped_rows"]]
    if len(parts) > 1:
        skipped_rows.sort(key=lambda r: (r["date_released"] or "", r["db_id"]), reverse=True)
        skipped_rows = skipped_rows[:SKIPPED_LIMIT]
    skipped_total = sum(reasons.values())

    return {
        "role": ",".join(roles),
        "roles": roles,
        "role_label": _role_label(roles),
        "sources": keys,
        "evaluator": {
            "user_id": user.id,
            "full_name": _full_name(user),
            "code": (user.alias or user.username or "").strip(),
            "position": user.position,
        },
        "filters": {
            "year": year,
            "month": month,
            "source": source if any(p["src_cond_used"] for p in parts) else None,
        },
        "summary": {
            "closed_apps": sum(p["closed_total"] for p in parts),
            "counted_apps": counted_n,
            "skipped_apps": skipped_total,
            "avg_tat": _r1(tat_sum / counted_n) if counted_n else None,
            "without_company": sum(p["no_company"] for p in parts),
            "without_generic": sum(p["no_generic"] for p in parts),
            "sources": sorted(
                (
                    {"start": a, "end": b, "count": n}
                    for (a, b), n in tat_sources.items()
                ),
                key=lambda x: -x["count"],
            ),
        },
        "period_mode": "year" if by_year else "month",
        "periods": periods,
        "companies": companies,
        "drugs": drugs,
        "skipped": {
            "total": skipped_total,
            "by_reason": [
                {"reason": k, "count": v}
                for k, v in sorted(reasons.items(), key=lambda x: -x[1])
            ],
            "shown": len(skipped_rows),
            "rows": skipped_rows,
        },
        "formula": _formula(roles, keys),
    }


# ── 3. Applications behind one company or drug row ───────────
def _records_one(db, S, user_id, kind, key, year, month, fetch, role, source):
    col = S.DRUG if kind == "drug" else S.COMPANY
    pa = _parts(db, S, role, user_id)
    days = pa.days
    rec, rel = S.dates()
    rel_ok = S.rel_ok(rel)
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
        scoped(spelling.label("sp"), func.count(S.ID).label("n"))
        .group_by(spelling)
        .all()
    )
    total_n, tat_sum = scoped(func.count(S.ID), func.sum(days)).one()
    rows = (
        scoped(
            S.ID.label("rid"),
            S.DTN.label("dtn"),
            S.COMPANY.label("company"),
            S.DRUG.label("drug"),
            S.BRAND.label("brand"),
            S.DOC.label("doc"),
            S.STATUS.label("status"),
            S.REC_RAW.label("rec_raw"),
            pa.start.label("tat_start"),
            pa.end.label("tat_end"),
            pa.start_src.label("start_src"),
            pa.end_src.label("end_src"),
            S.REL_RAW.label("rel_raw"),
            days.label("tat"),
        )
        .order_by(rel.desc(), S.ID.desc())
        .limit(fetch)
        .all()
    )
    return {
        "spellings": [{"name": r.sp, "count": int(r.n)} for r in sp_rows],
        "total": int(total_n or 0),
        "tat_sum": float(tat_sum or 0),
        "tat_n": int(total_n or 0),
        "rows": [_record_row(S, r, role) for r in rows],
    }


def _record_row(S, r, role):
    return {
        "source": S.key,
        "role": role,
        "db_id": r.rid,
        "dtn": str(r.dtn) if r.dtn else None,
        "company": _t(r.company),
        "generic_name": _t(" ".join(r.drug.split()) if S.key == "fgmp" and r.drug else r.drug),
        "brand_name": _t(r.brand),
        "doc_type": _t(r.doc),
        "status": _t(r.status),
        "date_received": _d(r.rec_raw),
        "tat_start": _d(r.tat_start),
        "tat_end": _d(r.tat_end),
        "tat_start_src": r.start_src,
        "tat_end_src": r.end_src,
        "date_released": _d(r.rel_raw),
        "tat": int(r.tat) if r.tat is not None else None,
    }


def _merge_records(results, page, page_size, sort_key):
    """Merge the per-source record lists: totals add up, rows are sorted again
    and cut to the requested page."""
    spell = {}
    for r in results:
        for s in r["spellings"]:
            spell[s["name"]] = spell.get(s["name"], 0) + s["count"]
    spellings = sorted(
        ({"name": n, "count": c} for n, c in spell.items()),
        key=lambda x: (-x["count"], x["name"] or ""),
    )
    rows = [row for r in results for row in r["rows"]]
    if len(results) > 1:
        rows.sort(key=sort_key, reverse=True)
    rows = rows[(page - 1) * page_size : page * page_size]
    tat_n = sum(r["tat_n"] for r in results)
    return {
        "spellings": spellings,
        "total": sum(r["total"] for r in results),
        "avg_tat": _r1(sum(r["tat_sum"] for r in results) / tat_n) if tat_n else None,
        "rows": rows,
    }


def get_evaluator_records(
    db: Session,
    user_id: int,
    kind: str,
    key: str,
    year: str = "All",
    month: str = "All",
    page: int = 1,
    page_size: int = 50,
    role="evaluator",
    source: str = None,
    sources="cpr",
):
    """The applications counted in one Company / Drug row of the monitoring.
    Same rules as get_evaluator_monitoring, so the total always matches the
    Total Apps number that was clicked."""
    roles = _role_list(role)
    kind = "drug" if kind == "drug" else "company"
    key = (key or "").strip().upper()
    units = _units(sources, roles)
    results = [
        _records_one(
            db, S, user_id, kind, key, year, month, page * page_size, r, source
        )
        for S, r in units
    ]
    m = _merge_records(
        results,
        page,
        page_size,
        lambda r: (r["date_released"] or "", r["source"], r["role"], r["db_id"]),
    )
    return {
        "role": ",".join(roles),
        "roles": roles,
        "role_label": _role_label(roles),
        "sources": list(dict.fromkeys(S.key for S, _ in units)),
        "kind": kind,
        "key": key,
        "name": m["spellings"][0]["name"] if m["spellings"] else None,
        "total": m["total"],
        "avg_tat": m["avg_tat"],
        "spellings": m["spellings"],
        "page": page,
        "page_size": page_size,
        "rows": m["rows"],
    }


# ── 5. Summary of one month ──────────────────────────────────
def _month_one(db, S, user_id, year, month, role):
    pa = _parts(db, S, role, user_id)
    days, tat_ok = pa.days, pa.tat_ok
    rec, rel = S.dates()
    rec_ok = S.rec_ok(rec)
    rel_ok = S.rel_ok(rel)

    def in_month(d):
        return and_(func.year(d) == year, func.month(d) == month)

    received_here = and_(rec_ok, in_month(rec))
    released_here = and_(rel_ok, in_month(rel))

    def q(*cols):
        return _handled(db, pa, user_id, *cols)

    def n(cond):
        return int(q(func.count(S.ID)).filter(cond).scalar() or 0)

    tat = (
        q(func.count(S.ID), func.sum(days), func.min(days), func.max(days))
        .filter(released_here, tat_ok)
        .one()
    )

    def ranking(key_expr, col, scope):
        spelling = _spelling(col)
        rows = (
            q(key_expr.label("k"), spelling.label("sp"), func.count(S.ID).label("n"))
            .filter(scope, ~_empty(col))
            .group_by(key_expr, spelling)
            .all()
        )
        groups = {}
        for r in rows:
            g = groups.setdefault(r.k, {"n": 0, "sp": {}})
            g["n"] += int(r.n)
            g["sp"][r.sp or ""] = g["sp"].get(r.sp or "", 0) + int(r.n)
        return groups

    def tops(scope):
        return {
            "companies": ranking(_norm(S.COMPANY), S.COMPANY, scope),
            "drugs": ranking(_norm(S.DRUG), S.DRUG, scope),
        }

    return {
        "received": n(received_here),
        "released": n(released_here),
        "still_open": n(and_(received_here, ~rel_ok)),
        "total": n(or_(received_here, released_here)),
        "tat": {
            "counted": int(tat[0] or 0),
            "sum": float(tat[1] or 0),
            "fastest": int(tat[2]) if tat[2] is not None else None,
            "slowest": int(tat[3]) if tat[3] is not None else None,
        },
        "received_top": tops(received_here),
        "released_top": tops(released_here),
    }


def _merge_top(per_source, side, kind, top):
    """Add up the company (or drug) groups of several sources and keep the
    biggest `top`."""
    merged = {}
    for p in per_source:
        for k, g in p[side][kind].items():
            m = merged.setdefault(k, {"n": 0, "sp": {}})
            m["n"] += g["n"]
            for name, c in g["sp"].items():
                m["sp"][name] = m["sp"].get(name, 0) + c
    items = [
        {"key": k, "name": max(m["sp"].items(), key=lambda x: (x[1], x[0]))[0], "count": m["n"]}
        for k, m in merged.items()
    ]
    items.sort(key=lambda x: (-x["count"], x["name"]))
    return items[:top], len(items)


def get_month_summary(
    db: Session,
    user_id: int,
    year: int,
    month: int,
    role="evaluator",
    top: int = 5,
    sources="cpr",
):
    """One month of one person: received / released / still open, the TAT of
    what was released that month, and the top companies and drugs of what was
    received and of what was released in the month."""
    roles = _role_list(role)
    units = _units(sources, roles)
    per = [_month_one(db, S, user_id, year, month, r) for S, r in units]

    def tops(side):
        companies, company_total = _merge_top(per, side, "companies", top)
        drugs, drug_total = _merge_top(per, side, "drugs", top)
        return {
            "companies": companies,
            "company_total": company_total,
            "drugs": drugs,
            "drug_total": drug_total,
        }

    counted = sum(p["tat"]["counted"] for p in per)
    tat_sum = sum(p["tat"]["sum"] for p in per)
    fast = [p["tat"]["fastest"] for p in per if p["tat"]["fastest"] is not None]
    slow = [p["tat"]["slowest"] for p in per if p["tat"]["slowest"] is not None]
    return {
        "role": ",".join(roles),
        "roles": roles,
        "role_label": _role_label(roles),
        "sources": list(dict.fromkeys(S.key for S, _ in units)),
        "year": year,
        "month": month,
        "label": f"{MONTH_ABBR[month]} {year}",
        "total_apps": sum(p["total"] for p in per),
        "received": sum(p["received"] for p in per),
        "released": sum(p["released"] for p in per),
        "still_open": sum(p["still_open"] for p in per),
        "tat": {
            "counted": counted,
            "avg": _r1(tat_sum / counted) if counted else None,
            "fastest": min(fast) if fast else None,
            "slowest": max(slow) if slow else None,
        },
        "received_top": tops("received_top"),
        "released_top": tops("released_top"),
        "no_doc_type": NO_DOC_TYPE,
    }


# ── 4. Applications behind one Received / Released number ────
def _period_one(
    db, S, user_id, side, bucket, year, other_year, other_month, rest, role,
    company_key, drug_key, doc_type, fetch,
):
    pa = _parts(db, S, role, user_id)
    days, tat_ok = pa.days, pa.tat_ok
    rec, rel = S.dates()
    rec_ok = S.rec_ok(rec)
    rel_ok = S.rel_ok(rel)

    by_year = year in (None, "", "All")

    def in_bucket(d):
        if by_year:
            return [func.year(d) == bucket]
        return [func.year(d) == int(year), func.month(d) == bucket]

    def on_other_side(d, ok):
        """the other side is in other_year (and other_month, when given)"""
        c = [ok, func.year(d) == other_year]
        if other_month is not None:
            c.append(func.month(d) == other_month)
        return c

    if side == "received":
        conds = [rec_ok, *in_bucket(rec)]
        if rest:
            conds.append(~rel_ok)
        elif other_year is not None:
            conds += on_other_side(rel, rel_ok)
        order = rec
    elif side == "released":
        conds = [rel_ok, *in_bucket(rel)]
        if rest:
            conds.append(~rec_ok)
        elif other_year is not None:
            conds += on_other_side(rec, rec_ok)
        order = rel
    else:  # either: received or released in the period
        conds = [
            or_(
                and_(rec_ok, *in_bucket(rec)),
                and_(rel_ok, *in_bucket(rel)),
            )
        ]
        order = func.coalesce(rec, rel)

    # optional: only one company / drug / document type (month summary)
    extra = []
    if company_key:
        extra.append(_norm(S.COMPANY) == company_key.strip().upper())
    if drug_key:
        extra.append(_norm(S.DRUG) == drug_key.strip().upper())
    if doc_type:
        extra.append(
            _empty(S.DOC) if doc_type == NO_DOC_TYPE else func.trim(S.DOC) == doc_type
        )

    def scoped(*cols):
        return _handled(db, pa, user_id, *cols).filter(*conds, *extra)

    total = int(scoped(func.count(S.ID)).scalar() or 0)
    tat_n, tat_sum = (
        scoped(func.count(S.ID), func.sum(days)).filter(tat_ok).one()
    )
    rows = (
        scoped(
            S.ID.label("rid"),
            S.DTN.label("dtn"),
            S.COMPANY.label("company"),
            S.DRUG.label("drug"),
            S.BRAND.label("brand"),
            S.DOC.label("doc"),
            S.STATUS.label("status"),
            S.REC_RAW.label("rec_raw"),
            pa.start.label("tat_start"),
            pa.end.label("tat_end"),
            pa.start_src.label("start_src"),
            pa.end_src.label("end_src"),
            S.REL_RAW.label("rel_raw"),
            case((tat_ok, days), else_=None).label("tat"),
            order.label("sort_date"),
        )
        .order_by(order.desc(), S.ID.desc())
        .limit(fetch)
        .all()
    )
    out_rows = []
    for r in rows:
        row = _record_row(S, r, role)
        row["_sort"] = _d(r.sort_date) or ""
        out_rows.append(row)
    return {
        "spellings": [],
        "total": total,
        "tat_sum": float(tat_sum or 0),
        "tat_n": int(tat_n or 0),
        "rows": out_rows,
    }


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
    role="evaluator",
    other_month: int = None,
    company_key: str = None,
    drug_key: str = None,
    doc_type: str = None,
    sources="cpr",
):
    """The applications counted in one Received or Released number of the
    Received / Released card (the whole number, or one part of its split).

    side="received": handled by the person and received in the period (open or
                     closed). other_year = released in that year, rest = not
                     released yet.
    side="released": closed and released in the period. other_year = received
                     in that year, rest = no received date.
    side="either":   received OR released in the period (a whole month row).
    other_month narrows other_year to one month of the other side.
    bucket is the year, or the month when a year is selected.
    """
    roles = _role_list(role)
    side = side if side in ("released", "either") else "received"
    units = _units(sources, roles)
    by_year = year in (None, "", "All")
    results = [
        _period_one(
            db, S, user_id, side, bucket, year, other_year, other_month, rest, r,
            company_key, drug_key, doc_type, page * page_size,
        )
        for S, r in units
    ]
    m = _merge_records(
        results,
        page,
        page_size,
        lambda r: (r["_sort"], r["source"], r["role"], r["db_id"]),
    )
    for row in m["rows"]:
        row.pop("_sort", None)

    label = str(bucket) if by_year else f"{MONTH_ABBR[bucket]} {year}"
    other_label = (
        f"{MONTH_ABBR[other_month]} {other_year}"
        if other_month is not None
        else str(other_year)
    )
    if side == "received":
        title = f"Received in {label}"
        if rest:
            title += " · not released yet"
        elif other_year is not None:
            title += f" · released in {other_label}"
    elif side == "released":
        title = f"Released in {label}"
        if rest:
            title += " · no received date"
        elif other_year is not None:
            title += f" · received in {other_label}"
    else:
        title = f"Received or released in {label}"

    return {
        "role": ",".join(roles),
        "roles": roles,
        "role_label": _role_label(roles),
        "sources": list(dict.fromkeys(S.key for S, _ in units)),
        "kind": "period",
        "side": side,
        "key": None,
        "name": title,
        "total": m["total"],
        "avg_tat": m["avg_tat"],
        "spellings": [],
        "page": page,
        "page_size": page_size,
        "rows": m["rows"],
    }
