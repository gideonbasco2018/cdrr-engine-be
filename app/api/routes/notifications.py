# app/api/routes/notifications.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.core.deadline_checker import run_deadline_notifications
from app.schemas.notification import (
    NotificationOut,
    NotificationUnreadCount,
    MarkReadResponse,
)
import app.crud.notification as crud_notif

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


# ── GET /api/notifications/{username} ────────────────────────────────
@router.get("/{username}", response_model=List[NotificationOut])
def get_notifications(
    username    : str,
    skip        : int  = Query(default=0,   ge=0),
    limit       : int  = Query(default=50,  le=200),
    unread_only : bool = Query(default=False),
    db          : Session = Depends(get_db),
):
    return crud_notif.get_notifications_by_user(
        db, username, skip=skip, limit=limit, unread_only=unread_only
    )


# ── GET /api/notifications/{username}/unread-count ───────────────────
@router.get("/{username}/unread-count", response_model=NotificationUnreadCount)
def get_unread_count(
    username: str,
    db      : Session = Depends(get_db),
):
    count = crud_notif.get_unread_count(db, username)
    return {"count": count}


# ── PATCH /api/notifications/{id}/read ───────────────────────────────
@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
def mark_as_read(
    notification_id: int,
    db             : Session = Depends(get_db),
):
    notif = crud_notif.get_notification_by_id(db, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    updated = crud_notif.mark_as_read(db, notification_id)
    return {"success": True, "updated": updated}


# ── PATCH /api/notifications/{username}/read-all ─────────────────────
@router.patch("/{username}/read-all", response_model=MarkReadResponse)
def mark_all_as_read(
    username: str,
    db      : Session = Depends(get_db),
):
    updated = crud_notif.mark_all_as_read(db, username)
    return {"success": True, "updated": updated}


# ── DELETE /api/notifications/{username}/clear-read ──────────────────
@router.delete("/{username}/clear-read", response_model=MarkReadResponse)
def clear_read_notifications(
    username: str,
    db      : Session = Depends(get_db),
):
    deleted = crud_notif.delete_read_notifications(db, username)
    return {"success": True, "updated": deleted}


# ── POST /api/notifications/trigger-deadline-check ───────────────────
# Para sa manual testing — hindi kailangan sa production
@router.post("/trigger-deadline-check")
def trigger_deadline_check():
    """Manually trigger the deadline checker for testing."""
    try:
        run_deadline_notifications()
        return {"success": True, "message": "Deadline check triggered successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deadline check failed: {str(e)}")