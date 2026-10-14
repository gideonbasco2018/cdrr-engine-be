# app/api/routes/sne_assignments.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.crud import sne_assignment as crud
from app.models.user import UserRole
from app.schemas.sne_assignment import (
    SneMemberOut,
    SneKeywordsIn,
    SneAssignmentCreate,
    SneAssignmentOut,
    SuggestIn,
    SuggestOut,
    WorkloadOut,
)
from app.services import sne_assignment_service as service

router = APIRouter(prefix="/api/sne-assignments", tags=["S&E Assignments"])


def require_admin(current_user):
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPERADMIN):
        raise HTTPException(status_code=403, detail="Not allowed.")


# ── Read ──────────────────────────────────────────────────────────────
@router.get("/members", response_model=List[SneMemberOut])
def list_members(
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    """S&E group members with their assigned keywords."""
    return service.get_members(db)


@router.get("/", response_model=List[SneAssignmentOut])
def list_assignments(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    return crud.get_all(db, user_id)


# ── Create ────────────────────────────────────────────────────────────
@router.post("/", response_model=SneAssignmentOut, status_code=201)
def add_assignment(
    body: SneAssignmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_admin(current_user)
    try:
        return service.add_keyword(db, body.user_id, body.keyword)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Update (replace all keywords of one member) ───────────────────────
@router.put("/members/{user_id}/keywords", response_model=SneMemberOut)
def replace_member_keywords(
    user_id: int,
    body: SneKeywordsIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_admin(current_user)
    try:
        return service.set_keywords(db, user_id, body.keywords)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Delete ────────────────────────────────────────────────────────────
@router.delete("/{assignment_id}", status_code=204)
def remove_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_admin(current_user)
    if not crud.delete(db, assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found.")


# ── Suggest (used by the Bulk Deck modal) ─────────────────────────────
@router.post("/suggest", response_model=SuggestOut)
def suggest(
    body: SuggestIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    items = [i.dict() for i in body.items]
    return {"assignments": service.suggest_assignments(db, items)}


@router.get("/workload", response_model=List[WorkloadOut])
def workload(
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user)
):
    """In-progress task counts per S&E member, grouped by step."""
    return service.get_workload(db)
