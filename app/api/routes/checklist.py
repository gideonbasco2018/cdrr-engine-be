# ============================================================
# FILE: app/api/routes/checklist.py
# ============================================================
"""Checklist routes — build a checklist of the DTNs in a forwarded
batch. The receiver scans each DTN (scanner gun) into a
checklist; the scan date/time is set by the server."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.checklist import (
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistResponse,
    ChecklistSummary,
)
from app.crud import checklist as crud

router = APIRouter(
    prefix="/api/checklist",
    tags=["Checklist"],
    dependencies=[Depends(get_current_active_user)],
)


def _display_name(user: User) -> str:
    """The user's alias, or their username when no alias is set."""
    return (user.alias or "").strip() or user.username


@router.get("", response_model=List[ChecklistSummary])
def list_checklists(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return crud.list_checklists(db, limit)


@router.post("", response_model=ChecklistResponse, status_code=201)
def create_checklist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return crud.create_checklist(db, _display_name(current_user))


@router.get("/{checklist_id}", response_model=ChecklistResponse)
def get_checklist(checklist_id: int, db: Session = Depends(get_db)):
    checklist = crud.get_checklist(db, checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found.")
    return checklist


@router.delete("/{checklist_id}", status_code=204)
def delete_checklist(checklist_id: int, db: Session = Depends(get_db)):
    if not crud.delete_checklist(db, checklist_id):
        raise HTTPException(status_code=404, detail="Checklist not found.")


@router.post("/{checklist_id}/items", response_model=ChecklistItemResponse, status_code=201)
def add_item(
    checklist_id: int,
    payload: ChecklistItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not crud.get_checklist(db, checklist_id):
        raise HTTPException(status_code=404, detail="Checklist not found.")
    try:
        return crud.add_item(db, checklist_id, payload.dtn, _display_name(current_user))
    except crud.DuplicateDtnError:
        raise HTTPException(status_code=409, detail=f"DTN {payload.dtn} is already in this checklist.")


@router.delete("/{checklist_id}/items/{item_id}", status_code=204)
def delete_item(checklist_id: int, item_id: int, db: Session = Depends(get_db)):
    if not crud.delete_item(db, checklist_id, item_id):
        raise HTTPException(status_code=404, detail="Item not found.")
