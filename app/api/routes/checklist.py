# ============================================================
# FILE: app/api/routes/checklist.py
# ============================================================
"""Checklist routes — build a checklist of the DTNs in a forwarded
batch. The receiver inserts each DTN into a checklist; the insert
date/time is set by the server."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.checklist import (
    ChecklistBinItemResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistResponse,
    ChecklistSummary,
    ChecklistUpdate,
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


@router.get("/server-time")
def server_time(db: Session = Depends(get_db)):
    """Current Manila time from the database — the same clock that stamps
    inserted_at — used for the "Generated:" line on the PDF / Excel so a
    wrong PC clock can't show on the printout. (Declared before
    /{checklist_id} so "server-time" isn't read as a checklist id.)"""
    now = db.execute(text("SELECT NOW()")).scalar()
    return {"now": now}


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


@router.patch("/{checklist_id}", response_model=ChecklistResponse)
def update_checklist(checklist_id: int, payload: ChecklistUpdate, db: Session = Depends(get_db)):
    """Set or clear the checklist's label (e.g. "URGENT", "CPR")."""
    checklist = crud.update_label(db, checklist_id, payload.label)
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found.")
    return checklist


@router.delete("/{checklist_id}", status_code=204)
def delete_checklist(
    checklist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft delete only — the checklist is hidden, never removed."""
    if not crud.soft_delete_checklist(db, checklist_id, _display_name(current_user)):
        raise HTTPException(status_code=404, detail="Checklist not found.")


@router.get("/{checklist_id}/bin", response_model=List[ChecklistBinItemResponse])
def list_bin(checklist_id: int, db: Session = Depends(get_db)):
    """Soft-removed DTNs of this checklist (is_removed = 1). Read-only — there is no restore."""
    if not crud.get_checklist(db, checklist_id):
        raise HTTPException(status_code=404, detail="Checklist not found.")
    return crud.list_bin(db, checklist_id)


@router.post("/{checklist_id}/items", response_model=ChecklistItemResponse, status_code=201)
def add_item(
    checklist_id: int,
    payload: ChecklistItemCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Saves the DTN right away (subject_status "pending"), then looks up its
    subject in FIS after the response is sent — a slow FIS never holds up
    the insert. The page picks the subject up a moment later."""
    if not crud.get_checklist(db, checklist_id):
        raise HTTPException(status_code=404, detail="Checklist not found.")
    try:
        item = crud.add_item(db, checklist_id, payload.dtn, _display_name(current_user))
    except crud.DuplicateDtnError:
        raise HTTPException(status_code=409, detail=f"DTN {payload.dtn} is already in this checklist.")
    background_tasks.add_task(crud.fill_subject_in_background, item.id, item.dtn)
    return item


@router.post("/{checklist_id}/subjects/refresh", response_model=ChecklistResponse)
def refresh_subjects(checklist_id: int, db: Session = Depends(get_db)):
    """Retry the FIS lookup for DTNs whose subject is still pending or failed
    (e.g. FIS was down when they were inserted)."""
    if not crud.get_checklist(db, checklist_id):
        raise HTTPException(status_code=404, detail="Checklist not found.")
    crud.refresh_subjects(db, checklist_id)
    db.expire_all()
    return crud.get_checklist(db, checklist_id)


@router.delete("/{checklist_id}/items/{item_id}", status_code=204)
def remove_item(
    checklist_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft remove — the DTN is flagged is_removed and shows in the Bin."""
    if not crud.get_checklist(db, checklist_id):
        raise HTTPException(status_code=404, detail="Checklist not found.")
    if not crud.remove_item(db, checklist_id, item_id, _display_name(current_user)):
        raise HTTPException(status_code=404, detail="Item not found.")
