# app/crud/target_assignment.py

from collections import defaultdict
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

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
)

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


# ── Lead assignment helpers ─────────────────────────────────────────
def get_active_lead_assignment(
    db: Session, lead_user_id: int, member_user_id: int
) -> Optional[LeadAssignment]:
    return (
        db.query(LeadAssignment)
        .filter(
            LeadAssignment.lead_user_id == lead_user_id,
            LeadAssignment.member_user_id == member_user_id,
            LeadAssignment.is_active == True,  # noqa: E712
        )
        .first()
    )


def get_my_team(db: Session, lead_user_id: int) -> List[LeadAssignment]:
    return (
        db.query(LeadAssignment)
        .filter(
            LeadAssignment.lead_user_id == lead_user_id,
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
                lead_role=a.lead_role,
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
        result.append(
            AllTeamsMemberOut(
                lead_assignment_id=a.id,
                member_user_id=a.member_user_id,
                member_name=(
                    f"{a.member.first_name} {a.member.surname}".strip()
                    if a.member
                    else ""
                ),
                lead_role=a.lead_role,
                assigned_at=a.assigned_at,
                task_count=count_member_tasks(db, a.member_user_id),
                target_count=count_member_targets(db, a.member_user_id),
                lead_user_id=a.lead_user_id,
                lead_name=(
                    f"{a.lead.first_name} {a.lead.surname}".strip() if a.lead else ""
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


# ── Member tasks (flattened application_logs + main_db + target state) ──
def get_member_tasks(db: Session, member_user_id: int) -> List[MemberTaskOut]:
    rows = (
        db.query(ApplicationLogs, MainDB, TargetAssignment)
        .join(MainDB, ApplicationLogs.main_db_id == MainDB.DB_ID)
        .outerjoin(
            TargetAssignment,
            (TargetAssignment.application_log_id == ApplicationLogs.id)
            & (TargetAssignment.is_active == True),  # noqa: E712
        )
        .filter(ApplicationLogs.user_id == member_user_id)
        .all()
    )

    main_db_ids = list({main.DB_ID for _, main, _ in rows})
    history_map = get_application_history_map(db, main_db_ids)

    result = []
    for log, main, target in rows:
        history = history_map.get(main.DB_ID, [])
        result.append(
            MemberTaskOut(
                log_id=log.id,
                db_id=main.DB_ID,
                dtn=main.DB_DTN,
                brand_name=main.DB_PROD_BR_NAME,
                step=log.application_step,
                status=log.application_status,
                entry_type=main.DB_ENTRY_TYPE or "ORIGINAL",
                app_type=main.DB_APP_TYPE,
                date_accomplished=log.accomplished_date,
                date_received_center=main.DB_DATE_RECEIVED_CENT,
                is_targeted=target is not None,
                target_assignment_id=target.id if target else None,
                target_start_date=target.target_start_date if target else None,
                target_end_date=target.target_end_date if target else None,
                target_remarks=target.remarks if target else None,
                application_progress_percent=compute_application_progress(history),
                application_history=build_application_history_entries(history),
            )
        )
    return result


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
