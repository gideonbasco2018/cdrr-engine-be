# app/crud/gmp_closed_tasks.py
"""FGMP "Close Task (Final)" — permanently close applications from the Queue.

Everything below happens in ONE database transaction, so a batch either closes
completely or not at all (CPR's version closes the task first and updates the
application in a second, separate step that can fail on its own):

  1. every OPEN task on every reference of the DTN is closed — in progress,
     unclaimed (OD Receiving / OD Releasing pool) and each person's task at the
     multi-assignee Signature Facilitator step;
  2. each reference gets status COMPLETED (a terminal status it already has,
     e.g. RELEASED or DISAPPROVED, is kept), its current step is cleared, and
     the released date is set if one was given;
  3. each changed field is written to the field audit log;
  4. one gmp_closed_tasks row per reference records who/when/why.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.gmp_record import GMPRecord, GMPApplicationLogs, GMPFieldAuditLog
from app.models.gmp_closed_task import GMPClosedTask
from app.schemas.gmp_closed_task import GMPCloseTasksRequest
from app.crud.gmp_record import GMP_TERMINAL_STATUSES, _normalize, _get_field_label

_PHT = timezone(timedelta(hours=8))
MAX_PER_BATCH = 50
STEP_CONTEXT = "Close Task (Final)"
ACTION_TYPE = "PERMANENT_CLOSE"


def _now_pht() -> datetime:
    return datetime.now(_PHT).replace(tzinfo=None)


class CloseBlocked(Exception):
    """The batch cannot be closed (already closed / not found). Nothing was written."""

    def __init__(self, message: str, errors: Dict):
        super().__init__(message)
        self.message = message
        self.errors = errors


def _label(rec: GMPRecord) -> str:
    return str(rec.GMP_DTN) if rec.GMP_DTN is not None else f"record {rec.GMP_ID}"


def get_closed_by_record_id(db: Session, record_id: int) -> Optional[GMPClosedTask]:
    return (
        db.query(GMPClosedTask)
        .filter(GMPClosedTask.gmp_record_id == record_id)
        .order_by(GMPClosedTask.closed_at.desc())
        .first()
    )


def close_dtns(
    db: Session, req: GMPCloseTasksRequest, user_id: int, user_name: str
) -> Tuple[List[dict], int, List[int]]:
    """Close every reference of the DTNs behind `req.record_ids`.

    Returns (per-DTN results, total logs closed, one record id per DTN).
    Raises CloseBlocked (nothing written) when any DTN is already closed or any
    id does not exist."""
    ids = list(dict.fromkeys(req.record_ids))
    selected = db.query(GMPRecord).filter(GMPRecord.GMP_ID.in_(ids)).all()

    not_found = [i for i in ids if i not in {r.GMP_ID for r in selected}]

    # Every live reference under each selected row's DTN.
    dtns = {r.GMP_DTN for r in selected if r.GMP_DTN is not None}
    refs: Dict[int, GMPRecord] = {r.GMP_ID: r for r in selected}
    if dtns:
        for r in (
            db.query(GMPRecord)
            .filter(
                GMPRecord.GMP_DTN.in_(dtns),
                or_(GMPRecord.GMP_TRASH.is_(None), GMPRecord.GMP_TRASH != "deleted"),
            )
            .all()
        ):
            refs[r.GMP_ID] = r

    # Already closed? (any reference of the DTN counts)
    already_closed = []
    if refs:
        closed_ids = {
            row[0]
            for row in db.query(GMPClosedTask.gmp_record_id)
            .filter(GMPClosedTask.gmp_record_id.in_(list(refs)))
            .all()
        }
        already_closed = sorted({_label(refs[i]) for i in closed_ids})

    errors: Dict = {}
    if already_closed:
        errors["already_closed"] = already_closed
    if not_found:
        errors["not_found"] = not_found
    if errors:
        raise CloseBlocked("Some applications could not be closed.", errors)

    now = _now_pht()
    ref_ids = list(refs)

    # 1. Every OPEN task on every reference (in progress, unclaimed, each assignee).
    open_logs = (
        db.query(GMPApplicationLogs)
        .filter(
            GMPApplicationLogs.gmp_record_id.in_(ref_ids),
            GMPApplicationLogs.del_thread == "Open",
        )
        .order_by(GMPApplicationLogs.del_index.asc())
        .all()
    )
    logs_by_record: Dict[int, List[GMPApplicationLogs]] = {}
    for log in open_logs:
        log.application_status = "COMPLETED"
        log.action_type = ACTION_TYPE
        if not (log.application_decision or "").strip():
            log.application_decision = f"Closed (final) — {req.reason_for_closing}"
        log.accomplished_date = now
        log.del_last_index = 0
        log.del_thread = "Close"
        logs_by_record.setdefault(log.gmp_record_id, []).append(log)

    # 2-4. Each reference: record fields, audit rows, closed-task row.
    by_dtn: Dict[str, dict] = {}
    for rid, rec in refs.items():
        before = {
            "GMP_APP_STATUS": rec.GMP_APP_STATUS,
            "GMP_CURRENT_STEP": rec.GMP_CURRENT_STEP,
            "GMP_RELEASED_DATE": rec.GMP_RELEASED_DATE,
        }
        # A terminal status the record already has (RELEASED, DISAPPROVED …) is kept.
        if (rec.GMP_APP_STATUS or "").strip().upper() not in GMP_TERMINAL_STATUSES:
            rec.GMP_APP_STATUS = "COMPLETED"
        rec.GMP_CURRENT_STEP = None
        if req.date_released is not None:
            rec.GMP_RELEASED_DATE = req.date_released
        after = {
            "GMP_APP_STATUS": rec.GMP_APP_STATUS,
            "GMP_CURRENT_STEP": rec.GMP_CURRENT_STEP,
            "GMP_RELEASED_DATE": rec.GMP_RELEASED_DATE,
        }

        rec_logs = logs_by_record.get(rid, [])
        session_id = str(uuid.uuid4())
        for field, new_val in after.items():
            old_val = before[field]
            if _normalize(old_val) == _normalize(new_val):
                continue
            db.add(GMPFieldAuditLog(
                gmp_record_id=rid,
                field_name=field,
                field_label=_get_field_label(field),
                old_value=_normalize(old_val),
                new_value=_normalize(new_val),
                action_type="UPDATE",
                gmp_log_id=rec_logs[-1].id if rec_logs else None,
                step_context=STEP_CONTEXT,
                session_id=session_id,
                user_name=user_name,
                user_id=user_id,
            ))

        db.add(GMPClosedTask(
            gmp_record_id=rid,
            dtn=rec.GMP_DTN,
            reference_no=rec.GMP_REFERENCE_NO,
            closed_by_user_id=user_id,
            closed_by_user_name=user_name,
            reason_for_closing=req.reason_for_closing,
            remarks=req.remarks,
            date_released=req.date_released,
            type_of_issuance_released=req.type_of_issuance_released,
            open_logs_closed=len(rec_logs),
            closed_at=now,
        ))

        key = _label(rec)
        entry = by_dtn.setdefault(
            key, {"dtn": key if rec.GMP_DTN is not None else None, "reference_nos": [], "open_logs_closed": 0, "_first_id": rid}
        )
        entry["reference_nos"].append(rec.GMP_REFERENCE_NO or "—")
        entry["open_logs_closed"] += len(rec_logs)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    results = [{k: v for k, v in e.items() if k != "_first_id"} for e in by_dtn.values()]
    first_ids = [e["_first_id"] for e in by_dtn.values()]
    return results, len(open_logs), first_ids
