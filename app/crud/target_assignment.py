# app/crud/target_assignment.py
from sqlalchemy import func, or_, String, Integer
from collections import defaultdict
from typing import List, Optional
from sqlalchemy.orm import Session


from app.models.user import User
from app.models.lead_assignment import LeadAssignment
from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB
from app.models.target_assignment import TargetAssignment
from app.schemas.target_assignment import (
    TargetAssignmentCreate,
    TargetAssignmentBulkCreate,
    TeamMemberOut,
    AllTeamsMemberOut,
    MemberTaskOut,
    ApplicationHistoryEntry,
    UnitTaskOut,
)

from app.models.directors_target import DirectorsTarget
from app.schemas.target_assignment import (
    TargetAssignmentCreate,
    TargetAssignmentBulkCreate,
    TeamMemberOut,
    AllTeamsMemberOut,
    MemberTaskOut,
    ApplicationHistoryEntry,
    DirectorsTargetCreate,
    DirectorsTargetBulkCreate,
    DirectorsTargetOut,
)
from app.models.directors_target import DirectorsTarget
from app.models.unit import Unit

# Status kinds treated as "terminal" (application is done, one way or
# another) — used by get_application_progress below. Kept in sync with
# the frontend's STATUS_KIND_MAP; update both if statuses change.
_DONE_STATUSES = {"COMPLETED", "CLOSED", "RELEASED"}
_STOPPED_STATUSES = {"CANCELLED", "CANCELED", "REJECTED", "DENIED"}

# ── Application progress: weighted per-stage checklist ──────────────
# ⚠️ CONFIRM/CORRECT these step_names with Gids — see the docstring on
# compute_application_progress() below for the full explanation.
APPLICATION_STAGE_WEIGHTS = [
    {"key": "quality_evaluation", "weight": 40, "step_names": ["Quality Evaluation"]},
    {"key": "checker", "weight": 10, "step_names": ["Checking"]},
    {"key": "supervisor", "weight": 10, "step_names": ["PRSDD Compliance"]},
    {"key": "qa_admin", "weight": 10, "step_names": ["PRSDD Chief Admin"]},
    {"key": "lrd_chief_admin", "weight": 10, "step_names": ["LRD Chief Admin"]},
    {"key": "od_receiving", "weight": 10, "step_names": ["OD-Receiving"]},
    {
        "key": "od_releasing",
        "weight": 10,
        "step_names": ["OD-Releasing", "Releasing Officer"],
    },
]
_TERMINAL_RELEASE_STEPS = {"OD-RELEASING", "RELEASING OFFICER"}


from app.models.unit import Unit  # idagdag sa imports sa taas ng file


def get_active_lead_assignment(
    db: Session, lead_user_id: int, member_user_id: int
) -> Optional[LeadAssignment]:
    return (
        db.query(LeadAssignment)
        .join(Unit, LeadAssignment.unit_id == Unit.id)
        .filter(
            Unit.lead_user_id == lead_user_id,
            LeadAssignment.member_user_id == member_user_id,
            LeadAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )


def get_my_team(db: Session, lead_user_id: int) -> List[LeadAssignment]:
    return (
        db.query(LeadAssignment)
        .join(Unit, LeadAssignment.unit_id == Unit.id)
        .filter(
            Unit.lead_user_id == lead_user_id,
            LeadAssignment.is_active == True,  # noqa: E712
        )
        .all()
    )


def count_member_tasks(db: Session, member_user_id: int) -> int:
    return (
        db.query(func.count(ApplicationLogs.id))
        .filter(ApplicationLogs.user_id == member_user_id)
        .scalar()
        or 0
    )


def count_member_directors_targets(db: Session, member_user_id: int) -> int:
    return (
        db.query(func.count(DirectorsTarget.id))
        .join(
            ApplicationLogs,
            DirectorsTarget.application_log_id == ApplicationLogs.id,
        )
        .filter(
            ApplicationLogs.user_id == member_user_id,
            DirectorsTarget.is_active == True,  # noqa: E712
        )
        .scalar()
        or 0
    )


def count_member_targets(db: Session, member_user_id: int) -> int:
    return (
        db.query(func.count(TargetAssignment.id))
        .join(
            ApplicationLogs,
            TargetAssignment.application_log_id == ApplicationLogs.id,
        )
        .filter(
            ApplicationLogs.user_id == member_user_id,
            TargetAssignment.is_active == True,  # noqa: E712
        )
        .scalar()
        or 0
    )


def build_team_overview(db: Session, lead_user_id: int) -> List[TeamMemberOut]:
    assignments = get_my_team(db, lead_user_id)

    result: List[TeamMemberOut] = []
    for a in assignments:
        result.append(
            TeamMemberOut(
                lead_assignment_id=a.id,
                member_user_id=a.member_user_id,
                member_name=(
                    f"{a.member.first_name} {a.member.surname}".strip()
                    if a.member
                    else ""
                ),
                lead_role=a.group.name if a.group else "",
                unit_id=a.unit_id,
                unit_name=a.unit.name if a.unit else "",
                assigned_at=a.assigned_at,
                task_count=count_member_tasks(db, a.member_user_id),
                target_count=count_member_targets(db, a.member_user_id),
            )
        )
    return result


# ── Monitoring: EVERY team, not just the current lead's ──────────────
def get_all_active_lead_assignments(db: Session) -> List[LeadAssignment]:
    return (
        db.query(LeadAssignment)
        .filter(LeadAssignment.is_active == True)  # noqa: E712
        .all()
    )


def build_all_teams_overview(db: Session) -> List[AllTeamsMemberOut]:
    assignments = get_all_active_lead_assignments(db)

    result: List[AllTeamsMemberOut] = []
    for a in assignments:
        unit = a.unit
        result.append(
            AllTeamsMemberOut(
                lead_assignment_id=a.id,
                member_user_id=a.member_user_id,
                member_name=(
                    f"{a.member.first_name} {a.member.surname}".strip()
                    if a.member
                    else ""
                ),
                lead_role=a.group.name if a.group else "",
                unit_id=a.unit_id,
                unit_name=unit.name if unit else "",
                assigned_at=a.assigned_at,
                task_count=count_member_tasks(db, a.member_user_id),
                target_count=count_member_targets(db, a.member_user_id),
                directors_target_count=count_member_directors_targets(
                    db, a.member_user_id
                ),
                in_progress_count=count_member_in_progress_tasks(
                    db, a.member_user_id
                ),  # ← bago
                lead_user_id=unit.lead_user_id if unit else None,
                lead_name=(
                    f"{unit.lead.first_name} {unit.lead.surname}".strip()
                    if unit and unit.lead
                    else ""
                ),
            )
        )
    return result


# ── Application progress (approximation — see module docstring note) ──
def get_application_history_map(db: Session, main_db_ids: List[int]) -> dict:
    """
    One query for ALL application_logs belonging to the given main_db_ids,
    grouped by main_db_id and ordered chronologically. Used to build both
    the progress bar and the hover "history" tooltip without an N+1 query
    per row.
    """
    if not main_db_ids:
        return {}
    history_rows = (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.main_db_id.in_(main_db_ids))
        .order_by(ApplicationLogs.main_db_id, ApplicationLogs.created_at.asc())
        .all()
    )
    grouped = defaultdict(list)
    for h in history_rows:
        grouped[h.main_db_id].append(h)
    return grouped


def compute_application_progress(history: List[ApplicationLogs]) -> float:
    """
    Weighted per-stage checklist (as specified by Gids):
      Quality Evaluation .......... 40%
      Checker  ..................... +10%
      Supervisor .................... +10%
      QA Admin ...................... +10%
      LRD Chief Admin ............... +10%
      OD-Receiving ................... +10%
      OD-Releasing .................... +10%   (sums to 100%)

    A stage is credited ONCE its step has EVER shown a "done" status
    (Completed/Closed/Released) anywhere in the application's full
    history — an existence check, not a running/current-step position.
    This means if a step bounces back later (e.g. sent back to Quality
    Evaluation for another round), the percentage does NOT drop and
    does NOT add extra points either — it just stays at whatever was
    already earned. The application only ever reads 100% once the
    releasing stage itself (OD-Releasing / "Releasing Officer") is
    completed — which is also the last stage below, so both conditions
    agree by construction.

    ⚠️ CONFIRM WITH GIDS: the `step_names` below are a best guess based
    on the literal `application_step` values seen so far (Quality
    Evaluation, Checking, PRSDD Compliance, PRSDD Chief Admin, LRD
    Chief Admin, OD-Receiving, OD-Releasing). "Checker" / "Supervisor" /
    "QA Admin" don't appear verbatim as step text anywhere I've seen —
    please verify/correct which literal step maps to each stage below.
    """
    if not history:
        return 0.0

    def is_done(log: ApplicationLogs) -> bool:
        return (log.application_status or "").strip().upper() in _DONE_STATUSES

    # Terminal: the releasing step itself is completed -> 100%, full stop.
    for h in history:
        step_key = (h.application_step or "").strip().upper()
        if step_key in _TERMINAL_RELEASE_STEPS and is_done(h):
            return 100.0

    total = 0
    for stage in APPLICATION_STAGE_WEIGHTS:
        names = {n.strip().upper() for n in stage["step_names"]}
        earned = any(
            (h.application_step or "").strip().upper() in names and is_done(h)
            for h in history
        )
        if earned:
            total += stage["weight"]

    return min(100.0, float(total))


def build_application_history_entries(
    history: List[ApplicationLogs],
) -> List[ApplicationHistoryEntry]:
    return [
        ApplicationHistoryEntry(
            step=h.application_step,
            status=h.application_status,
            date=h.start_date or h.created_at,
            decision=h.application_decision,
            user_name=h.user_name,
        )
        for h in history
    ]


def get_member_tasks(db: Session, member_user_id: int) -> List[MemberTaskOut]:

    rows = (
        db.query(ApplicationLogs, MainDB, TargetAssignment, DirectorsTarget)
        .join(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .outerjoin(
            TargetAssignment,
            (TargetAssignment.application_log_id == ApplicationLogs.id)
            & (TargetAssignment.is_active == True),  # noqa: E712
        )
        .outerjoin(
            DirectorsTarget,
            (DirectorsTarget.application_log_id == ApplicationLogs.id)
            & (DirectorsTarget.is_active == True),  # noqa: E712
        )
        .filter(ApplicationLogs.user_id == member_user_id)
        .all()
    )

    main_db_ids = list({main.DB_ID for _, main, _, _ in rows})
    history_map = get_application_history_map(db, main_db_ids)

    return [
        _build_member_task_out(
            log, main, target, dtarget, history_map.get(main.DB_ID, [])
        )
        for log, main, target, dtarget in rows
    ]


# ── Target assignment mutations ─────────────────────────────────────
def get_application_log(
    db: Session, application_log_id: int
) -> Optional[ApplicationLogs]:
    return (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.id == application_log_id)
        .first()
    )


def get_active_target_by_log(
    db: Session, application_log_id: int
) -> Optional[TargetAssignment]:
    return (
        db.query(TargetAssignment)
        .filter(
            TargetAssignment.application_log_id == application_log_id,
            TargetAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )


def get_target_by_log(
    db: Session, application_log_id: int
) -> Optional[TargetAssignment]:
    """Fetches the row regardless of is_active — used to decide upsert vs insert."""
    return (
        db.query(TargetAssignment)
        .filter(TargetAssignment.application_log_id == application_log_id)
        .first()
    )


def mark_as_target(
    db: Session,
    *,
    log: ApplicationLogs,
    lead_assignment: LeadAssignment,
    lead_user_id: int,
    payload: TargetAssignmentCreate,
) -> TargetAssignment:
    existing = get_target_by_log(db, payload.application_log_id)

    if existing:
        existing.is_active = True
        existing.remarks = payload.remarks
        existing.target_start_date = payload.target_start_date
        existing.target_end_date = payload.target_end_date
        existing.lead_user_id = lead_user_id
        existing.lead_assignment_id = lead_assignment.id
        existing.untargeted_at = None
        db.commit()
        db.refresh(existing)
        return existing

    new_target = TargetAssignment(
        application_log_id=log.id,
        main_db_id=log.main_db_id,
        member_user_id=log.user_id,
        lead_user_id=lead_user_id,
        lead_assignment_id=lead_assignment.id,
        remarks=payload.remarks,
        target_start_date=payload.target_start_date,
        target_end_date=payload.target_end_date,
        is_active=True,
    )
    db.add(new_target)
    db.commit()
    db.refresh(new_target)
    return new_target


def unmark_as_target(db: Session, target: TargetAssignment) -> TargetAssignment:
    target.is_active = False
    target.untargeted_at = func.now()
    db.commit()
    db.refresh(target)
    return target


def get_application_logs_by_ids(
    db: Session, application_log_ids: List[int]
) -> List[ApplicationLogs]:
    return (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.id.in_(application_log_ids))
        .all()
    )


def bulk_mark_as_target(
    db: Session,
    *,
    logs: List[ApplicationLogs],
    lead_assignment_by_member: dict,
    lead_user_id: int,
    payload: TargetAssignmentBulkCreate,
) -> List[TargetAssignment]:
    """
    Marks several application_logs as target in one go, all with the same
    date range/remarks. lead_assignment_by_member maps member_user_id ->
    the LeadAssignment already validated by the route (one lookup per
    distinct member instead of per log).
    """
    results: List[TargetAssignment] = []

    for log in logs:
        lead_assignment = lead_assignment_by_member[log.user_id]
        existing = get_target_by_log(db, log.id)

        if existing:
            existing.is_active = True
            existing.remarks = payload.remarks
            existing.target_start_date = payload.target_start_date
            existing.target_end_date = payload.target_end_date
            existing.lead_user_id = lead_user_id
            existing.lead_assignment_id = lead_assignment.id
            existing.untargeted_at = None
            results.append(existing)
        else:
            new_target = TargetAssignment(
                application_log_id=log.id,
                main_db_id=log.main_db_id,
                member_user_id=log.user_id,
                lead_user_id=lead_user_id,
                lead_assignment_id=lead_assignment.id,
                remarks=payload.remarks,
                target_start_date=payload.target_start_date,
                target_end_date=payload.target_end_date,
                is_active=True,
            )
            db.add(new_target)
            results.append(new_target)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


# ── Director's Target mutations ─────────────────────────────────────
def get_active_directors_target_by_log(
    db: Session, application_log_id: int
) -> Optional[DirectorsTarget]:
    return (
        db.query(DirectorsTarget)
        .filter(
            DirectorsTarget.application_log_id == application_log_id,
            DirectorsTarget.is_active == True,  # noqa: E712
        )
        .first()
    )


def get_directors_target_by_log(
    db: Session, application_log_id: int
) -> Optional[DirectorsTarget]:
    """Fetches the row regardless of is_active — used to decide upsert vs insert."""
    return (
        db.query(DirectorsTarget)
        .filter(DirectorsTarget.application_log_id == application_log_id)
        .first()
    )


def mark_as_directors_target(
    db: Session,
    *,
    log: ApplicationLogs,
    targeted_by_user_id: int,
    payload: DirectorsTargetCreate,
) -> DirectorsTarget:
    existing = get_directors_target_by_log(db, payload.application_log_id)

    if existing:
        existing.is_active = True
        existing.remarks = payload.remarks
        existing.target_start_date = payload.target_start_date
        existing.target_end_date = payload.target_end_date
        existing.targeted_by_user_id = targeted_by_user_id
        existing.targeted_at = func.now()
        existing.untargeted_at = None
        db.commit()
        db.refresh(existing)
        return existing

    new_target = DirectorsTarget(
        application_log_id=log.id,
        main_db_id=log.main_db_id,
        member_user_id=log.user_id,
        targeted_by_user_id=targeted_by_user_id,
        remarks=payload.remarks,
        target_start_date=payload.target_start_date,
        target_end_date=payload.target_end_date,
        is_active=True,
    )
    db.add(new_target)
    db.commit()
    db.refresh(new_target)
    return new_target


def bulk_mark_as_directors_target(
    db: Session,
    *,
    logs: List[ApplicationLogs],
    targeted_by_user_id: int,
    payload: DirectorsTargetBulkCreate,
) -> List[DirectorsTarget]:
    results: List[DirectorsTarget] = []

    for log in logs:
        existing = get_directors_target_by_log(db, log.id)

        if existing:
            existing.is_active = True
            existing.remarks = payload.remarks
            existing.target_start_date = payload.target_start_date
            existing.target_end_date = payload.target_end_date
            existing.targeted_by_user_id = targeted_by_user_id
            existing.targeted_at = func.now()
            existing.untargeted_at = None
            results.append(existing)
        else:
            new_target = DirectorsTarget(
                application_log_id=log.id,
                main_db_id=log.main_db_id,
                member_user_id=log.user_id,
                targeted_by_user_id=targeted_by_user_id,
                remarks=payload.remarks,
                target_start_date=payload.target_start_date,
                target_end_date=payload.target_end_date,
                is_active=True,
            )
            db.add(new_target)
            results.append(new_target)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


def unmark_as_directors_target(db: Session, target: DirectorsTarget) -> DirectorsTarget:
    target.is_active = False
    target.untargeted_at = func.now()
    db.commit()
    db.refresh(target)
    return target


_TERMINAL_STATUSES = _DONE_STATUSES | _STOPPED_STATUSES


def _build_member_task_out(log, main, target, dtarget, history) -> MemberTaskOut:
    return MemberTaskOut(
        log_id=log.id,
        db_id=main.DB_ID,
        dtn=main.DB_DTN,
        brand_name=main.DB_PROD_BR_NAME,
        step=log.application_step,
        status=log.application_status,
        entry_type=main.DB_ENTRY_TYPE or "ORIGINAL",
        app_type=main.DB_APP_TYPE,
        # ── NEW: Product Class + Processing Type — previously missing,
        #    which is why these columns rendered blank on the FE table.
        #    ⚠️ CONFIRM the exact MainDB attribute names with Gids/DBA —
        #    these follow the same DB_<COLUMN> naming convention as the
        #    other MainDB fields above (DB_PROD_CLASS_PRESCRIP maps to
        #    prod_class_prescrip, DB_PROCESSING_TYPE maps to
        #    processing_type). Adjust if the actual model attrs differ. ──
        prod_class_prescrip=getattr(main, "DB_PROD_CLASS_PRESCRIP", None),
        processing_type=getattr(main, "DB_PROCESSING_TYPE", None),
        date_accomplished=log.accomplished_date,
        date_received_center=main.DB_DATE_RECEIVED_CENT,
        is_targeted=target is not None,
        target_assignment_id=target.id if target else None,
        target_start_date=target.target_start_date if target else None,
        target_end_date=target.target_end_date if target else None,
        target_remarks=target.remarks if target else None,
        application_progress_percent=compute_application_progress(history),
        application_history=build_application_history_entries(history),
        is_directors_target=dtarget is not None,
        directors_target_start_date=(dtarget.target_start_date if dtarget else None),
        directors_target_end_date=(dtarget.target_end_date if dtarget else None),
        directors_target_remarks=dtarget.remarks if dtarget else None,
    )


def count_member_in_progress_tasks(db: Session, member_user_id: int) -> int:
    """
    Kinokonsidera NULL status bilang 'in progress' din (hindi pa
    natatapos), hindi lang mga status na hindi galing sa terminal list.
    """
    status_expr = func.upper(func.trim(ApplicationLogs.application_status))
    return (
        db.query(func.count(ApplicationLogs.id))
        .filter(
            ApplicationLogs.user_id == member_user_id,
            or_(
                ApplicationLogs.application_status.is_(None),
                status_expr.notin_(_TERMINAL_STATUSES),
            ),
        )
        .scalar()
        or 0
    )


# ── Shared server-side filtering/sorting for in-progress task lists ──
# Used by BOTH get_member_in_progress_tasks_paginated (single member)
# and get_unit_in_progress_tasks_paginated (whole unit), so filtering
# behaves identically on both tables and stays accurate regardless of
# which page is currently loaded — filtering client-side against only
# the loaded page silently misses matches that live on other pages.
def _apply_in_progress_task_filters(
    query,
    *,
    dtn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    step: str | None = None,
    app_type: str | None = None,
    product_class: str | None = None,
    processing_type: str | None = None,
    entry_type: str | None = None,
    member_name: str | None = None,
    directors_target: str | None = None,
):
    """
    Applies every optional filter to the query. All comparisons are
    case-insensitive "contains" matches (ILIKE), except directors_target
    (exact state) and the date range.

    NOTE: date_from/date_to compare directly against
    MainDB.DB_DATE_RECEIVED_CENT as a plain string. This only produces
    correct chronological ordering if the column is consistently stored
    as an ISO 'YYYY-MM-DD' string. ⚠️ Please confirm this holds for all
    rows — if the column can be stored in another format, this needs a
    real date cast instead of a string comparison.
    """
    if dtn:
        like = f"%{dtn}%"
        query = query.filter(
            or_(
                func.cast(MainDB.DB_DTN, String).ilike(like),
                MainDB.DB_PROD_BR_NAME.ilike(like),
            )
        )

    if date_from:
        query = query.filter(MainDB.DB_DATE_RECEIVED_CENT >= date_from)
    if date_to:
        query = query.filter(MainDB.DB_DATE_RECEIVED_CENT <= date_to)

    if step:
        query = query.filter(ApplicationLogs.application_step.ilike(f"%{step}%"))

    if app_type:
        query = query.filter(MainDB.DB_APP_TYPE.ilike(f"%{app_type}%"))

    if product_class:
        query = query.filter(
            getattr(MainDB, "DB_PROD_CLASS_PRESCRIP").ilike(f"%{product_class}%")
        )

    if processing_type:
        query = query.filter(
            getattr(MainDB, "DB_PROCESSING_TYPE").ilike(f"%{processing_type}%")
        )

    if entry_type:
        # The frontend displays "ORIGINAL" whenever the underlying column
        # is NULL (see _build_member_task_out), so a search for
        # "original" must also match NULL rows, not just an exact stored
        # "ORIGINAL" value, or the row would disappear from the results
        # even though the UI shows it as a match.
        like = f"%{entry_type}%"
        conditions = [MainDB.DB_ENTRY_TYPE.ilike(like)]
        if entry_type.strip().lower() in "original":
            conditions.append(MainDB.DB_ENTRY_TYPE.is_(None))
        query = query.filter(or_(*conditions))

    if member_name:
        like = f"%{member_name}%"
        query = query.filter(
            or_(
                User.first_name.ilike(like),
                User.surname.ilike(like),
                func.concat(User.first_name, " ", User.surname).ilike(like),
            )
        )

    if directors_target == "targeted":
        query = query.filter(DirectorsTarget.id.isnot(None))
    elif directors_target == "not_targeted":
        query = query.filter(DirectorsTarget.id.is_(None))

    return query


# ── Column map for server-side sorting. Keys match the frontend
#    TaskTable column keys 1:1, so the FE can send sort_by=<column key>
#    straight from a header click with no translation table on either
#    side. ──
def _sortable_columns():
    return {
        "dtn": MainDB.DB_DTN,
        "date_received_center": MainDB.DB_DATE_RECEIVED_CENT,
        "prod_class_prescrip": getattr(MainDB, "DB_PROD_CLASS_PRESCRIP", None),
        "app_type": MainDB.DB_APP_TYPE,
        "processing_type": getattr(MainDB, "DB_PROCESSING_TYPE", None),
        "entry_type": MainDB.DB_ENTRY_TYPE,
        "step": ApplicationLogs.application_step,
        "member_name": User.first_name,
    }


def _apply_in_progress_task_sort(query, sort_by: str | None, sort_dir: str | None):
    if not sort_by:
        return query

    if sort_by == "directors_target":
        # Sort by whether the row currently has an active Director's
        # Target (targeted rows first when descending).
        sort_col = func.coalesce(func.cast(DirectorsTarget.id.isnot(None), Integer), 0)
    else:
        sort_col = _sortable_columns().get(sort_by)

    if sort_col is None:
        return query  # unknown sort_by — ignore instead of erroring

    return query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())


def get_member_in_progress_tasks_paginated(
    db: Session,
    member_user_id: int,
    skip: int = 0,
    limit: int = 20,
    *,
    dtn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    step: str | None = None,
    app_type: str | None = None,
    product_class: str | None = None,
    processing_type: str | None = None,
    entry_type: str | None = None,
    directors_target: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
):
    """
    Considers NULL status as "in progress" too, not just a status that's
    outside the terminal list.

    Switched the MainDB join to LEFT (outer) instead of INNER, for the
    same reason as the unit-wide version below: a task with no matching
    MainDB row should still show up (with fallback display values)
    instead of silently disappearing from the list and its count.
    """
    status_expr = func.upper(func.trim(ApplicationLogs.application_status))
    base_query = (
        db.query(ApplicationLogs, MainDB, TargetAssignment, DirectorsTarget)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .outerjoin(
            TargetAssignment,
            (TargetAssignment.application_log_id == ApplicationLogs.id)
            & (TargetAssignment.is_active == True),  # noqa: E712
        )
        .outerjoin(
            DirectorsTarget,
            (DirectorsTarget.application_log_id == ApplicationLogs.id)
            & (DirectorsTarget.is_active == True),  # noqa: E712
        )
        .filter(
            ApplicationLogs.user_id == member_user_id,
            or_(
                ApplicationLogs.application_status.is_(None),
                status_expr.notin_(_TERMINAL_STATUSES),
            ),
        )
    )

    base_query = _apply_in_progress_task_filters(
        base_query,
        dtn=dtn,
        date_from=date_from,
        date_to=date_to,
        step=step,
        app_type=app_type,
        product_class=product_class,
        processing_type=processing_type,
        entry_type=entry_type,
        directors_target=directors_target,
    )

    # Count AFTER filters, BEFORE sort/pagination, so `total` reflects
    # every matching row across all pages.
    total = base_query.count()

    base_query = _apply_in_progress_task_sort(base_query, sort_by, sort_dir)
    if not sort_by:
        base_query = base_query.order_by(ApplicationLogs.created_at.desc())

    rows = base_query.offset(skip).limit(limit).all()

    main_db_ids = list({main.DB_ID for _, main, _, _ in rows if main is not None})
    history_map = get_application_history_map(db, main_db_ids)

    result = [
        _build_member_task_out_safe(
            log,
            main,
            target,
            dtarget,
            history_map.get(main.DB_ID if main else None, []),
        )
        for log, main, target, dtarget in rows
    ]
    return result, total


def _group_unit_in_progress(
    db: Session, unit_id: int, group_col, fallback_label: str = "Unspecified"
) -> List[dict]:
    """
    Reusable grouped-count query — bilang ng in-progress tasks ng isang
    unit, grouped by kung anong column ang ipasa (step, app type, prod
    class, processing type). Counts lang, walang task rows na kinukuha.
    Kailangan ng LEFT JOIN sa MainDB dahil ang app_type/prod_class/
    processing_type ay nandoon, hindi sa ApplicationLogs.
    """
    status_expr = func.upper(func.trim(ApplicationLogs.application_status))
    rows = (
        db.query(
            func.coalesce(group_col, fallback_label).label("label"),
            func.count(ApplicationLogs.id).label("count"),
        )
        .join(LeadAssignment, LeadAssignment.member_user_id == ApplicationLogs.user_id)
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .filter(
            LeadAssignment.unit_id == unit_id,
            LeadAssignment.is_active == True,  # noqa: E712
            or_(
                ApplicationLogs.application_status.is_(None),
                status_expr.notin_(_TERMINAL_STATUSES),
            ),
        )
        .group_by(group_col)
        .order_by(func.count(ApplicationLogs.id).desc())
        .all()
    )
    return [{"label": r.label, "count": r.count} for r in rows]


def get_unit_in_progress_summary(db: Session, unit_id: int) -> dict:
    """
    Multi-grouping breakdown para sa Directors Diagram: by step, by app
    type, by product classification, by processing type — lahat sa
    isang response, para hindi na kailangan 4 hiwalay na tawag mula sa FE.
    ⚠️ CONFIRM MainDB attr names DB_PROD_CLASS_PRESCRIP / DB_PROCESSING_TYPE
    sa Gids/DBA — same caveat sa _build_member_task_out sa taas.
    """
    return {
        "by_step": _group_unit_in_progress(
            db, unit_id, ApplicationLogs.application_step
        ),
        "by_app_type": _group_unit_in_progress(db, unit_id, MainDB.DB_APP_TYPE),
        "by_product_class": _group_unit_in_progress(
            db, unit_id, getattr(MainDB, "DB_PROD_CLASS_PRESCRIP", None)
        ),
        "by_processing_type": _group_unit_in_progress(
            db, unit_id, getattr(MainDB, "DB_PROCESSING_TYPE", None)
        ),
    }


def get_unit_in_progress_tasks_paginated(
    db: Session,
    unit_id: int,
    skip: int = 0,
    limit: int = 20,
    step: str | None = None,
    app_type: str | None = None,
    product_class: str | None = None,
    processing_type: str | None = None,
    *,
    dtn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    entry_type: str | None = None,
    member_name: str | None = None,
    directors_target: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
):
    """
    All in-progress tasks for an entire unit (all active members),
    combined into one paginated list. Uses LEFT JOIN to MainDB and User
    so a row is never silently dropped just because it has no matching
    MainDB entry or User record — it still appears, with fallback
    values on the display fields instead.

    Every filter is applied server-side via _apply_in_progress_task_filters
    so `total` and the returned rows stay accurate no matter which page
    is requested. Filtering only the current page client-side would
    under-report matches once there is more than one page.
    """
    status_expr = func.upper(func.trim(ApplicationLogs.application_status))
    base_query = (
        db.query(ApplicationLogs, MainDB, TargetAssignment, DirectorsTarget, User)
        .join(
            LeadAssignment,
            (LeadAssignment.member_user_id == ApplicationLogs.user_id)
            & (LeadAssignment.unit_id == unit_id)
            & (LeadAssignment.is_active == True),  # noqa: E712
        )
        .outerjoin(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .outerjoin(User, User.id == ApplicationLogs.user_id)
        .outerjoin(
            TargetAssignment,
            (TargetAssignment.application_log_id == ApplicationLogs.id)
            & (TargetAssignment.is_active == True),  # noqa: E712
        )
        .outerjoin(
            DirectorsTarget,
            (DirectorsTarget.application_log_id == ApplicationLogs.id)
            & (DirectorsTarget.is_active == True),  # noqa: E712
        )
        .filter(
            or_(
                ApplicationLogs.application_status.is_(None),
                status_expr.notin_(_TERMINAL_STATUSES),
            )
        )
    )

    base_query = _apply_in_progress_task_filters(
        base_query,
        dtn=dtn,
        date_from=date_from,
        date_to=date_to,
        step=step,
        app_type=app_type,
        product_class=product_class,
        processing_type=processing_type,
        entry_type=entry_type,
        member_name=member_name,
        directors_target=directors_target,
    )

    total = base_query.count()

    base_query = _apply_in_progress_task_sort(base_query, sort_by, sort_dir)
    if not sort_by:
        base_query = base_query.order_by(ApplicationLogs.created_at.desc())

    rows = base_query.offset(skip).limit(limit).all()

    main_db_ids = list({main.DB_ID for _, main, _, _, _ in rows if main is not None})
    history_map = get_application_history_map(db, main_db_ids)

    result = []
    for log, main, target, dtarget, user in rows:
        history = history_map.get(main.DB_ID, []) if main else []
        base = _build_member_task_out_safe(log, main, target, dtarget, history)
        resolved_member_name = (
            f"{user.first_name} {user.surname}".strip() if user else None
        )
        result.append(
            UnitTaskOut(
                **base.model_dump(),
                member_user_id=log.user_id,
                member_name=resolved_member_name or "Unknown member",
            )
        )
    return result, total


def _build_member_task_out_safe(log, main, target, dtarget, history) -> MemberTaskOut:
    """
    Same as _build_member_task_out, but null-safe for `main` — since the
    join is now LEFT instead of INNER, it's possible for a task to have
    no matching MainDB row at all.
    """
    if main is None:
        return MemberTaskOut(
            log_id=log.id,
            db_id=log.main_db_id or 0,
            dtn=None,
            brand_name="(no matching record)",
            step=log.application_step,
            status=log.application_status,
            entry_type="ORIGINAL",
            app_type=None,
            prod_class_prescrip=None,
            processing_type=None,
            date_accomplished=log.accomplished_date,
            date_received_center=None,
            is_targeted=target is not None,
            target_assignment_id=target.id if target else None,
            target_start_date=target.target_start_date if target else None,
            target_end_date=target.target_end_date if target else None,
            target_remarks=target.remarks if target else None,
            application_progress_percent=0.0,
            application_history=[],
            is_directors_target=dtarget is not None,
            directors_target_start_date=(
                dtarget.target_start_date if dtarget else None
            ),
            directors_target_end_date=(dtarget.target_end_date if dtarget else None),
            directors_target_remarks=dtarget.remarks if dtarget else None,
        )
    return _build_member_task_out(log, main, target, dtarget, history)
