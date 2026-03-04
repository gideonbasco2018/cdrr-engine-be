# app/crud/notification.py

from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import date, timedelta
from typing import List, Optional

from app.models.notification import Notification
from app.schemas.notification import NotificationCreate


# ─────────────────────────────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────────────────────────────

def get_notifications_by_user(
    db       : Session,
    user_name: str,
    skip     : int = 0,
    limit    : int = 50,
    unread_only: bool = False,
) -> List[Notification]:
    """Get notifications for a user, newest first."""
    query = db.query(Notification).filter(Notification.user_name == user_name)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return (
        query
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_unread_count(db: Session, user_name: str) -> int:
    return (
        db.query(func.count(Notification.id))
        .filter(Notification.user_name == user_name, Notification.is_read == False)
        .scalar()
    )


def get_notification_by_id(db: Session, notification_id: int) -> Optional[Notification]:
    return db.query(Notification).filter(Notification.id == notification_id).first()


def already_notified_today(
    db        : Session,
    user_name : str,
    link_dtn  : str,
    title_like: Optional[str] = None,
) -> bool:
    """
    Duplicate guard — returns True if a notification was already
    created for this user + DTN today.
    """
    today = date.today()
    query = (
        db.query(Notification)
        .filter(
            Notification.user_name == user_name,
            Notification.link_dtn  == link_dtn,
            cast(Notification.created_at, Date) == today,
        )
    )
    if title_like:
        query = query.filter(Notification.title.ilike(f"%{title_like}%"))
    return query.first() is not None


# ─────────────────────────────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────────────────────────────

def create_notification(db: Session, data: NotificationCreate) -> Notification:
    notif = Notification(**data.model_dump())
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def bulk_create_notifications(db: Session, items: List[NotificationCreate]) -> int:
    """Batch insert — returns count of created notifications."""
    notifs = [Notification(**item.model_dump()) for item in items]
    db.add_all(notifs)
    db.commit()
    return len(notifs)


# ─────────────────────────────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────────────────────────────

def mark_as_read(db: Session, notification_id: int) -> int:
    """Returns number of rows updated."""
    updated = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return updated


def mark_all_as_read(db: Session, user_name: str) -> int:
    """Mark all unread notifications as read for a user."""
    updated = (
        db.query(Notification)
        .filter(Notification.user_name == user_name, Notification.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return updated


# ─────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────

def delete_read_notifications(db: Session, user_name: str) -> int:
    """Clear already-read notifications for a user."""
    deleted = (
        db.query(Notification)
        .filter(Notification.user_name == user_name, Notification.is_read == True)
        .delete()
    )
    db.commit()
    return deleted


def delete_old_notifications(db: Session, days_old: int = 30) -> int:
    """
    Cleanup job — delete notifications older than N days.
    Recommended: run weekly via cron.
    """
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    deleted = (
        db.query(Notification)
        .filter(Notification.created_at < cutoff, Notification.is_read == True)
        .delete()
    )
    db.commit()
    return deleted


# ─────────────────────────────────────────────────────────────────────
# DEADLINE CHECKER HELPERS
# ─────────────────────────────────────────────────────────────────────

def _add_working_days(start: date, days: int) -> date:
    """Returns the date that is N working days (Mon–Fri) from start."""
    count = 0
    current = start
    while count < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 0=Mon … 4=Fri
            count += 1
    return current


def get_approaching_deadline_logs(db: Session, working_days_away: int = 3):
    """
    Returns application_logs whose deadline_date is exactly
    N working days from today and are still IN PROGRESS.
    Used by the cron job.
    """
    from app.models.application_logs import ApplicationLogs

    today       = date.today()
    target_date = _add_working_days(today, working_days_away)

    return (
        db.query(ApplicationLogs)
        .filter(
            ApplicationLogs.application_status  == "IN PROGRESS",
            ApplicationLogs.deadline_date       == target_date,
            ApplicationLogs.deadline_date.isnot(None),
        )
        .all()
    )


def get_due_today_logs(db: Session):
    """Returns logs whose deadline is TODAY and still IN PROGRESS."""
    from app.models.application_logs import ApplicationLogs

    today = date.today()
    return (
        db.query(ApplicationLogs)
        .filter(
            ApplicationLogs.application_status == "IN PROGRESS",
            ApplicationLogs.deadline_date      == today,
        )
        .all()
    )