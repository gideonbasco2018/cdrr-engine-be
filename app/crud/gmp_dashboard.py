# app/crud/gmp_dashboard.py
# GMP counterpart of app/crud/dashboard.py — same received/completed/on_process
# semantics, scoped to GMPApplicationLogs instead of ApplicationLogs.

from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional
from datetime import date

from app.models.gmp_record import GMPApplicationLogs, GMPRecord
from app.crud.gmp_logs import _assignee_match


def _base_query(
    db: Session,
    username: str,
    user_id: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
):
    # Matched by user_id OR user_name (see _assignee_match) — username alone
    # broke the moment a user was renamed, silently dropping every log
    # recorded under their old username from every KPI on this dashboard.
    #
    # Restricted to PRIMARY ('-01') reference numbers only, same guard
    # get_tasks_for_user uses (app/crud/gmp_logs.py) — a DTN can have sibling
    # GMPRecord rows (added via Add Issuance), and only the primary one
    # should ever carry logs going forward, but legacy data sometimes has
    # logs on a sibling too. Without this, an affected DTN inflates every KPI
    # here (counted once per sibling instead of once).
    q = (
        db.query(GMPApplicationLogs)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .filter(
            _assignee_match(username, user_id),
            GMPApplicationLogs.del_thread.in_(["Close", "Open"]),
            or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01")),
        )
    )
    if date_from:
        q = q.filter(GMPApplicationLogs.start_date >= date_from)
    if date_to:
        q = q.filter(func.date(GMPApplicationLogs.start_date) <= date_to)
    return q


def get_total_received(
    db: Session,
    username: str,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    return _base_query(db, username, user_id, date_from, date_to).count()


def get_total_completed(
    db: Session,
    username: str,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    return (
        _base_query(db, username, user_id, date_from, date_to)
        .filter(GMPApplicationLogs.application_status == "COMPLETED")
        .count()
    )


def get_total_on_process(
    db: Session,
    username: str,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> int:
    return (
        _base_query(db, username, user_id, date_from, date_to)
        .filter(
            GMPApplicationLogs.application_status == "IN PROGRESS",
            GMPApplicationLogs.del_thread == "Open",
        )
        .count()
    )


def get_stats_summary(
    db: Session,
    username: str,
    user_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    received = get_total_received(db, username, user_id, date_from, date_to)
    completed = get_total_completed(db, username, user_id, date_from, date_to)
    on_process = get_total_on_process(db, username, user_id, date_from, date_to)

    return {
        "received": received,
        "completed": completed,
        "on_process": on_process,
    }
