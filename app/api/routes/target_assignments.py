# app/api/routes/target_assignments.py

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User, UserRole
from app.crud import target_assignment as crud_target_assignment
from app.schemas.target_assignment import (
    TargetAssignmentCreate,
    TargetAssignmentBulkCreate,
    TargetAssignmentOut,
    TeamMemberOut,
    AllTeamsMemberOut,
    MemberTaskOut,
)

router = APIRouter(
    prefix="/api/target_assignments",
    tags=["Target Assignments "],
)


def _require_admin(current_user: User) -> None:
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admins only.",
        )


# ── GET /api/lead-assignments/my-team ───────────────────────────────
@router.get("/lead-assignments/my-team", response_model=List[TeamMemberOut])
def get_my_team(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return crud_target_assignment.build_team_overview(db, current_user.id)


# ── GET /api/lead-assignments/my-team/{member_user_id}/tasks ───────
@router.get(
    "/lead-assignments/my-team/{member_user_id}/tasks",
    response_model=List[MemberTaskOut],
)
def get_member_tasks(
    member_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    is_my_member = crud_target_assignment.get_active_lead_assignment(
        db, lead_user_id=current_user.id, member_user_id=member_user_id
    )
    if not is_my_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This user is not on your team.",
        )
    return crud_target_assignment.get_member_tasks(db, member_user_id)


# ── GET /api/lead-assignments/all-teams ─────────────────────────────
# Monitoring/admin view — EVERY active lead assignment across the org,
# not just the current user's own team.
@router.get("/lead-assignments/all-teams", response_model=List[AllTeamsMemberOut])
def get_all_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    return crud_target_assignment.build_all_teams_overview(db)


# ── GET /api/lead-assignments/all-teams/{member_user_id}/tasks ─────
# Same task list as get_member_tasks, but without the "is this user on
# MY team" check — admins can look at anyone's tasks.
@router.get(
    "/lead-assignments/all-teams/{member_user_id}/tasks",
    response_model=List[MemberTaskOut],
)
def get_all_teams_member_tasks(
    member_user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _require_admin(current_user)
    return crud_target_assignment.get_member_tasks(db, member_user_id)


# ── POST /api/target-assignments/bulk ────────────────────────────────
# NOTE: dapat NAUUNA ito bago yung DELETE .../{application_log_id}
@router.post("/target-assignments/bulk", response_model=List[TargetAssignmentOut])
def bulk_mark_as_target(
    payload: TargetAssignmentBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    logs = crud_target_assignment.get_application_logs_by_ids(
        db, payload.application_log_ids
    )
    if not logs:
        raise HTTPException(status_code=404, detail="No application logs found.")

    found_ids = {log.id for log in logs}
    missing_ids = set(payload.application_log_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Application logs not found: {sorted(missing_ids)}",
        )

    lead_assignment_by_member = {}
    for log in logs:
        if not log.user_id:
            raise HTTPException(
                status_code=400,
                detail=f"Task {log.id} has no assigned member yet.",
            )
        if log.user_id not in lead_assignment_by_member:
            lead_assignment = crud_target_assignment.get_active_lead_assignment(
                db, lead_user_id=current_user.id, member_user_id=log.user_id
            )
            if not lead_assignment:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You are not the lead for the user holding task {log.id}.",
                )
            lead_assignment_by_member[log.user_id] = lead_assignment

    return crud_target_assignment.bulk_mark_as_target(
        db,
        logs=logs,
        lead_assignment_by_member=lead_assignment_by_member,
        lead_user_id=current_user.id,
        payload=payload,
    )


# ── POST /api/target-assignments ────────────────────────────────────
@router.post("/target-assignments", response_model=TargetAssignmentOut)
def mark_as_target(
    payload: TargetAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    log = crud_target_assignment.get_application_log(db, payload.application_log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Application log not found.")
    if not log.user_id:
        raise HTTPException(
            status_code=400,
            detail="This task has no assigned member yet.",
        )

    lead_assignment = crud_target_assignment.get_active_lead_assignment(
        db, lead_user_id=current_user.id, member_user_id=log.user_id
    )
    if not lead_assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the lead for the user holding this task.",
        )

    return crud_target_assignment.mark_as_target(
        db,
        log=log,
        lead_assignment=lead_assignment,
        lead_user_id=current_user.id,
        payload=payload,
    )


# ── DELETE /api/target-assignments/{application_log_id} ─────────────
@router.delete("/target-assignments/{application_log_id}", status_code=204)
def unmark_as_target(
    application_log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    target = crud_target_assignment.get_active_target_by_log(db, application_log_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found.")

    if target.lead_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the lead who targeted this task can unmark it.",
        )

    crud_target_assignment.unmark_as_target(db, target)
    return None
