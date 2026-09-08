# app/crud/gmp_post_eval_status.py
# "Post-Evaluation Status" — FGMP Dashboard-only card. Answers "what have I
# finished my part on that isn't released yet, and where is it now?" for the
# logged-in Evaluator / Checker / any other FGMP step owner. No CPR
# counterpart — this is scoped to GMPRecord / GMPApplicationLogs only.

from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, Dict
import math

from app.models.gmp_record import GMPApplicationLogs, GMPRecord
from app.crud.gmp_logs import _assignee_match


def _my_active_record_ids(db: Session, username: Optional[str], user_id: Optional[int]):
    """
    Every GMPRecord where the current user COMPLETED at least one step, and
    the application is still actively moving — GMP_CURRENT_STEP is only
    cleared to NULL once the workflow truly ends (Released, or Disapproved;
    see the "final step" branch of advance_step in app/crud/gmp_logs.py), so
    a non-null value here means someone else now holds it.

    Restricted to PRIMARY ('-01') reference numbers only, same guard
    get_tasks_for_user uses (app/crud/gmp_logs.py) — a DTN can have sibling
    GMPRecord rows (added via Add Issuance), and only the primary one should
    ever carry logs going forward, but legacy data sometimes has logs on a
    sibling too. Without this, a DTN with that legacy pattern shows up twice.
    """
    return (
        db.query(GMPApplicationLogs.gmp_record_id)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .filter(
            _assignee_match(username, user_id),
            GMPApplicationLogs.application_status == "COMPLETED",
            GMPRecord.GMP_CURRENT_STEP.isnot(None),
            or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01")),
        )
        .distinct()
    )


def get_step_breakdown(
    db: Session, username: Optional[str], user_id: Optional[int] = None
) -> Dict[str, int]:
    """{current_step: count} — one entry per step something is currently
    sitting at, e.g. {"QA Admin": 1, "Checker": 5, "OD Releasing": 3}."""
    ids_subq = _my_active_record_ids(db, username, user_id).subquery()
    rows = (
        db.query(GMPRecord.GMP_CURRENT_STEP, func.count(GMPRecord.GMP_ID))
        .filter(GMPRecord.GMP_ID.in_(db.query(ids_subq.c.gmp_record_id)))
        .group_by(GMPRecord.GMP_CURRENT_STEP)
        .all()
    )
    return {step: count for step, count in rows if step}


def get_rows(
    db: Session,
    username: Optional[str],
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """One row per application (never per log — a user can complete more than
    one step on the same record over its life; this collapses to their most
    recent completed step on it)."""
    page = max(1, page)
    page_size = max(1, min(50, page_size))

    ids_subq = _my_active_record_ids(db, username, user_id).subquery()
    base = db.query(GMPRecord).filter(
        GMPRecord.GMP_ID.in_(db.query(ids_subq.c.gmp_record_id))
    )

    total = base.count()
    total_pages = max(1, math.ceil(total / page_size))
    records = (
        base.order_by(GMPRecord.GMP_ID.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    record_ids = [r.GMP_ID for r in records]

    # "Your step" — this user's most recently completed log per record.
    # Ordered so, within each record_id group, the highest del_index (most
    # recent) comes first; setdefault then keeps only that first hit.
    my_step_by_record = {}
    if record_ids:
        my_logs = (
            db.query(GMPApplicationLogs)
            .filter(
                GMPApplicationLogs.gmp_record_id.in_(record_ids),
                _assignee_match(username, user_id),
                GMPApplicationLogs.application_status == "COMPLETED",
            )
            .order_by(
                GMPApplicationLogs.gmp_record_id,
                GMPApplicationLogs.del_index.desc(),
            )
            .all()
        )
        for log in my_logs:
            my_step_by_record.setdefault(log.gmp_record_id, log)

    rows = []
    for r in records:
        my_log = my_step_by_record.get(r.GMP_ID)
        rows.append({
            "gmp_id": r.GMP_ID,
            "dtn": str(r.GMP_DTN) if r.GMP_DTN is not None else None,
            "lto_company": r.GMP_LTO_COMPANY,
            "your_step": my_log.application_step if my_log else None,
            "completed_date": my_log.accomplished_date if my_log else None,
            "current_step": r.GMP_CURRENT_STEP,
        })

    return {"rows": rows, "total": total, "total_pages": total_pages, "page": page}
