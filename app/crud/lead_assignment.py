# app/crud/lead_assignment.py

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta

from app.models.lead_assignment import LeadAssignment
from app.schemas.lead_assignment import (
    LeadAssignmentCreate,
    LeadAssignmentUpdate,
    LeadAssignmentBatchCreate,
)

PHT = timezone(timedelta(hours=8))


def get_all_lead_assignments(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    unit_id: Optional[int] = None,
    member_user_id: Optional[int] = None,
    group_id: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Tuple[List[LeadAssignment], int]:

    query = db.query(LeadAssignment)

    if unit_id is not None:
        query = query.filter(LeadAssignment.unit_id == unit_id)
    if member_user_id is not None:
        query = query.filter(LeadAssignment.member_user_id == member_user_id)
    if group_id is not None:
        query = query.filter(LeadAssignment.group_id == group_id)
    if is_active is not None:
        query = query.filter(LeadAssignment.is_active == is_active)

    total = query.count()
    data = (
        query.order_by(LeadAssignment.assigned_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return data, total


def get_lead_assignment_by_id(
    db: Session,
    assignment_id: int,
) -> Optional[LeadAssignment]:
    return db.query(LeadAssignment).filter(LeadAssignment.id == assignment_id).first()


def create_lead_assignment(
    db: Session,
    payload: LeadAssignmentCreate,
    assigned_by_user_id: Optional[int] = None,
) -> LeadAssignment:
    # Prevent duplicate active assignment (same member, same unit, same role)
    existing = (
        db.query(LeadAssignment)
        .filter(
            and_(
                LeadAssignment.unit_id == payload.unit_id,
                LeadAssignment.member_user_id == payload.member_user_id,
                LeadAssignment.group_id == payload.group_id,
                LeadAssignment.is_active == True,
            )
        )
        .first()
    )

    if existing:
        return existing  # idempotent — return existing na lang

    assignment = LeadAssignment(
        unit_id=payload.unit_id,
        member_user_id=payload.member_user_id,
        group_id=payload.group_id,
        remarks=payload.remarks,
        assigned_by_user_id=assigned_by_user_id,
        is_active=True,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def update_lead_assignment(
    db: Session,
    assignment_id: int,
    payload: LeadAssignmentUpdate,
) -> Optional[LeadAssignment]:
    assignment = get_lead_assignment_by_id(db, assignment_id)
    if not assignment:
        return None

    if payload.is_active is not None:
        assignment.is_active = payload.is_active
        # Auto-set unassigned_at kapag na-deactivate
        if not payload.is_active and not assignment.unassigned_at:
            assignment.unassigned_at = datetime.now(PHT).replace(tzinfo=None)

    if payload.remarks is not None:
        assignment.remarks = payload.remarks

    if payload.group_id is not None:
        assignment.group_id = payload.group_id

    db.commit()
    db.refresh(assignment)
    return assignment


def delete_lead_assignment(
    db: Session,
    assignment_id: int,
) -> bool:
    assignment = get_lead_assignment_by_id(db, assignment_id)
    if not assignment:
        return False
    db.delete(assignment)
    db.commit()
    return True


def get_member_ids_under_unit(
    db: Session,
    unit_id: int,
    group_id: Optional[int] = None,
) -> List[int]:
    """
    Returns list of member user IDs under a specific unit (+ optional
    role filter). Used for monitoring queries.
    """
    query = db.query(LeadAssignment.member_user_id).filter(
        LeadAssignment.unit_id == unit_id,
        LeadAssignment.is_active == True,
    )
    if group_id is not None:
        query = query.filter(LeadAssignment.group_id == group_id)
    return [row[0] for row in query.all()]


def batch_create_lead_assignments(
    db: Session,
    payload: LeadAssignmentBatchCreate,
    assigned_by_user_id: Optional[int] = None,
) -> List[LeadAssignment]:
    created = []
    for member_id in payload.member_user_ids:
        # skip kung may existing na active assignment
        existing = (
            db.query(LeadAssignment)
            .filter(
                and_(
                    LeadAssignment.unit_id == payload.unit_id,
                    LeadAssignment.member_user_id == member_id,
                    LeadAssignment.group_id == payload.group_id,
                    LeadAssignment.is_active == True,
                )
            )
            .first()
        )
        if existing:
            continue

        assignment = LeadAssignment(
            unit_id=payload.unit_id,
            member_user_id=member_id,
            group_id=payload.group_id,
            remarks=payload.remarks,
            assigned_by_user_id=assigned_by_user_id,
            is_active=True,
        )
        db.add(assignment)
        created.append(assignment)

    if created:
        db.commit()
        for a in created:
            db.refresh(a)

    return created
