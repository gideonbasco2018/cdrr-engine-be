# app/crud/unit.py

from sqlalchemy.orm import Session
from typing import Optional, List, Tuple

from app.models.unit import Unit
from app.models.lead_assignment import LeadAssignment
from app.schemas.unit import UnitCreate, UnitUpdate


def get_all_units(
    db: Session, skip: int = 0, limit: int = 100, is_active: Optional[bool] = None
) -> Tuple[List[dict], int]:
    query = db.query(Unit)
    if is_active is not None:
        query = query.filter(Unit.is_active == is_active)

    total = query.count()
    units = query.order_by(Unit.name.asc()).offset(skip).limit(limit).all()

    result = []
    for u in units:
        member_count = (
            db.query(LeadAssignment)
            .filter(
                LeadAssignment.unit_id == u.id, LeadAssignment.is_active == True
            )  # noqa: E712
            .count()
        )
        result.append({"unit": u, "member_count": member_count})
    return result, total


def get_unit_by_id(db: Session, unit_id: int) -> Optional[Unit]:
    return db.query(Unit).filter(Unit.id == unit_id).first()


def create_unit(db: Session, payload: UnitCreate) -> Unit:
    unit = Unit(
        name=payload.name,
        description=payload.description,
        lead_user_id=payload.lead_user_id,
        qa_admin_user_id=payload.qa_admin_user_id,
        is_active=True,
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def update_unit(db: Session, unit_id: int, payload: UnitUpdate) -> Optional[Unit]:
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        return None

    if payload.name is not None:
        unit.name = payload.name
    if payload.description is not None:
        unit.description = payload.description
    if payload.lead_user_id is not None:
        unit.lead_user_id = payload.lead_user_id
    if payload.qa_admin_user_id is not None:
        unit.qa_admin_user_id = payload.qa_admin_user_id
    if payload.is_active is not None:
        unit.is_active = payload.is_active

    db.commit()
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit_id: int) -> bool:
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        return False
    db.delete(unit)  # cascades to lead_assignments — see Unit.assignments cascade
    db.commit()
    return True
