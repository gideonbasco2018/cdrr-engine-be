# app/crud/target_assignment.py

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
    MemberTaskOut,
)


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

    return [
        MemberTaskOut(
            log_id=log.id,
            db_id=main.DB_ID,
            dtn=main.DB_DTN,
            brand_name=main.DB_PROD_BR_NAME,
            step=log.application_step,
            status=log.application_status,
            date_accomplished=log.accomplished_date,
            date_received_center=main.DB_DATE_RECEIVED_CENT,
            is_targeted=target is not None,
            target_assignment_id=target.id if target else None,
            target_start_date=target.target_start_date if target else None,
            target_end_date=target.target_end_date if target else None,
            target_remarks=target.remarks if target else None,
        )
        for log, main, target in rows
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
