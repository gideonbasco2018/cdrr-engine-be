# app/routers/lead_assignment.py

import math
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.crud.lead_assignment import (
    get_all_lead_assignments,
    get_lead_assignment_by_id,
    create_lead_assignment,
    update_lead_assignment,
    delete_lead_assignment,
    batch_create_lead_assignments,
)
from app.schemas.lead_assignment import (
    LeadAssignmentCreate,
    LeadAssignmentUpdate,
    LeadAssignmentResponse,
    LeadAssignmentListResponse,
    LeadAssignmentBatchCreate,
)

router = APIRouter(
    prefix="/api/lead_assignments",
    tags=["Lead Assignments"],
)


@router.get("/", response_model=LeadAssignmentListResponse)
def list_lead_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    unit_id: Optional[int] = Query(None),
    member_user_id: Optional[int] = Query(None),
    group_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get a paginated list of lead assignments.

    Supports filtering by unit, member user, functional role/group
    within the unit (Checker/Evaluator, Evaluator, Preassessor, etc.),
    and active status.
    """
    skip = (page - 1) * page_size
    data, total = get_all_lead_assignments(
        db=db,
        skip=skip,
        limit=page_size,
        unit_id=unit_id,
        member_user_id=member_user_id,
        group_id=group_id,
        is_active=is_active,
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "data": data,
    }


@router.get("/{assignment_id}", response_model=LeadAssignmentResponse)
def get_lead_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get a single lead assignment by its ID."""
    assignment = get_lead_assignment_by_id(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.post("/", response_model=LeadAssignmentResponse, status_code=201)
def create_assignment(
    payload: LeadAssignmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Assign a member to a unit under a specific functional role (group)."""
    return create_lead_assignment(
        db=db,
        payload=payload,
        assigned_by_user_id=current_user.id,
    )


@router.patch("/{assignment_id}", response_model=LeadAssignmentResponse)
def update_assignment(
    assignment_id: int,
    payload: LeadAssignmentUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update an existing lead assignment by its ID."""
    assignment = update_lead_assignment(db, assignment_id, payload)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete a lead assignment by its ID."""
    deleted = delete_lead_assignment(db, assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")


@router.post("/batch", response_model=List[LeadAssignmentResponse], status_code=201)
def batch_create_assignments(
    payload: LeadAssignmentBatchCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Assign multiple members to the same unit + functional role in a
    single request, all recorded under the current user as the assigner.
    """
    return batch_create_lead_assignments(
        db=db,
        payload=payload,
        assigned_by_user_id=current_user.id,
    )
