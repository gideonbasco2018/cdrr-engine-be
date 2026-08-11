# app/routers/units.py

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.crud.unit import (
    get_all_units,
    get_unit_by_id,
    create_unit,
    update_unit,
    delete_unit,
)
from app.schemas.unit import UnitCreate, UnitUpdate, UnitResponse, UnitListResponse

router = APIRouter(prefix="/api/units", tags=["Units"])


@router.get("/", response_model=UnitListResponse)
def list_units(
    is_active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List all units (e.g. 'Facilitated Registration Pathway Unit'), each
    with its head, QA admin, and active member count."""
    rows, total = get_all_units(db, skip=0, limit=500, is_active=is_active)
    data = []
    for r in rows:
        unit_out = UnitResponse.model_validate(r["unit"])
        unit_out.member_count = r["member_count"]
        data.append(unit_out)
    return {"total": total, "data": data}


@router.get("/{unit_id}", response_model=UnitResponse)
def get_unit(
    unit_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    unit = get_unit_by_id(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@router.post("/", response_model=UnitResponse, status_code=201)
def create_new_unit(
    payload: UnitCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return create_unit(db, payload)


@router.patch("/{unit_id}", response_model=UnitResponse)
def update_existing_unit(
    unit_id: int,
    payload: UnitUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    unit = update_unit(db, unit_id, payload)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@router.delete("/{unit_id}", status_code=204)
def delete_existing_unit(
    unit_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """⚠️ Deletes the unit AND all its member assignments (cascade)."""
    deleted = delete_unit(db, unit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Unit not found")
