# app/crud/gmp_dashboard.py
# GMP counterpart of app/crud/dashboard.py — same received/completed/on_process
# semantics, scoped to GMPApplicationLogs instead of ApplicationLogs.

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date

from app.models.gmp_record import GMPApplicationLogs


def _base_query(
    db: Session,
    username: str,
    date_from: Optional[date],
    date_to: Optional[date],
):
    q = db.query(GMPApplicationLogs).filter(
        GMPApplicationLogs.user_name == username,
        GMPApplicationLogs.del_thread.in_(["Close", "Open"]),
    )
    if date_from:
        q = q.filter(GMPApplicationLogs.start_date >= date_from)
    if date_to:
        q = q.filter(func.date(GMPApplicationLogs.start_date) <= date_to)
    return q


def get_total_received(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    return _base_query(db, username, date_from, date_to).count()


def get_total_completed(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    return (
        _base_query(db, username, date_from, date_to)
        .filter(GMPApplicationLogs.application_status == "COMPLETED")
        .count()
    )


def get_total_on_process(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    return (
        _base_query(db, username, date_from, date_to)
        .filter(
            GMPApplicationLogs.application_status == "IN PROGRESS",
            GMPApplicationLogs.del_thread == "Open",
        )
        .count()
    )


def get_stats_summary(
    db: Session,
    username: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    received = get_total_received(db, username, date_from, date_to)
    completed = get_total_completed(db, username, date_from, date_to)
    on_process = get_total_on_process(db, username, date_from, date_to)

    return {
        "received": received,
        "completed": completed,
        "on_process": on_process,
    }
