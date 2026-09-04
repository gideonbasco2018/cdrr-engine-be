# app/crud/gmp_logs.py
"""
CRUD for GMPApplicationLogs.
Mirrors the production app/crud/application_logs.py pattern:
  - advance_step  : close current log + open next
  - update_log    : patch an existing log (decision, remarks, doctrack, etc.)
  - reassign      : close current log + open new for different assignee
  - reroute       : close current log + open new at a different step
  - mark_received : flip is_received = 1
  - toggle_star   : flip is_starred
  - get_last_index: highest del_index for a record
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone, timedelta
from app.models.gmp_record import GMPApplicationLogs, GMPRecord
from app.crud.notification import create_notification, already_notified_today
from app.schemas.notification import NotificationCreate

_PHT = timezone(timedelta(hours=8))


def _now() -> datetime:
    """Current time in Philippine Standard Time, timezone-naive for DB storage."""
    return datetime.now(_PHT).replace(tzinfo=None)


# ─────────────────────────────────────────────────────────────────────────────
# Notification helper
# ─────────────────────────────────────────────────────────────────────────────
# Mirrors app/crud/application_logs.py's _notify_assigned_user, adapted for the
# GMP workflow's step names. app_log_id is intentionally left unset — the
# Notification.app_log_id FK points at application_logs.id, not
# gmp_application_logs.id, so setting it here would either violate the FK or
# (silently) point at the wrong table. link_dtn is enough for the bell to
# deep-link back to the record.

_GMP_ASSIGNED_TITLES = {
    "Decking": "📋 New GMP Decking Task",
    "Evaluator": "🔬 New GMP Evaluator Task",
    "Checker": "✅ New GMP Checker Task",
    "QA Admin": "🏢 New GMP QA Admin Task",
    "LRD Chief Admin": "🏛️ New GMP LRD Chief Admin Task",
    "OD Receiving": "📥 New GMP OD Receiving Task",
    "OD Releasing": "📤 New GMP OD Releasing Task",
    "FROO": "🔗 New GMP FROO Task",
}

_GMP_ASSIGNED_MESSAGES = {
    "Decking": "DTN {dtn} has been decked and assigned to you for processing.",
    "Evaluator": "You have been assigned a GMP Evaluator task for DTN: {dtn}.",
    "Checker": "You have been assigned a GMP Checker task for DTN: {dtn}.",
    "QA Admin": "You have been assigned a GMP QA Admin task for DTN: {dtn}.",
    "LRD Chief Admin": "You have been assigned a GMP LRD Chief Admin task for DTN: {dtn}.",
    "OD Receiving": "You have been assigned a GMP OD Receiving task for DTN: {dtn}.",
    "OD Releasing": "You have been assigned a GMP OD Releasing task for DTN: {dtn}.",
    "FROO": "DTN {dtn} requires FROO processing.",
}


def get_gmp_dtn(db: Session, gmp_record_id: int) -> str:
    """Fetch the DTN string from the parent GMPRecord, falling back to the raw ID."""
    try:
        record = db.query(GMPRecord).filter(GMPRecord.GMP_ID == gmp_record_id).first()
        if record and record.GMP_DTN is not None:
            return str(record.GMP_DTN)
    except Exception:
        pass
    return str(gmp_record_id)


def _notify_gmp_assigned(db: Session, log_obj: GMPApplicationLogs, dtn: str) -> None:
    """
    Create a notification for the user who was just assigned an IN PROGRESS
    GMP task. Silently skips on any error so it never breaks the main flow.
    """
    try:
        if log_obj.application_status != "IN PROGRESS":
            return
        if not log_obj.user_name:
            return

        step = log_obj.application_step or ""
        title = _GMP_ASSIGNED_TITLES.get(step, f"📌 New GMP Task: {step}")
        msg = _GMP_ASSIGNED_MESSAGES.get(
            step,
            f"You have a new GMP task for DTN: {dtn}.",
        ).format(dtn=dtn)

        # One notification per user + DTN + step per day
        if already_notified_today(db, log_obj.user_name, dtn, title_like=step):
            return

        create_notification(
            db,
            NotificationCreate(
                user_name=log_obj.user_name,
                title=title,
                message=msg,
                link_dtn=dtn,
            ),
        )
    except Exception:
        pass  # notification failure must never crash the main operation


# ─────────────────────────────────────────────────────────────────────────────
# Basic getters
# ─────────────────────────────────────────────────────────────────────────────

def get_log_by_id(db: Session, log_id: int) -> Optional[GMPApplicationLogs]:
    return db.query(GMPApplicationLogs).filter(GMPApplicationLogs.id == log_id).first()


def get_last_index(db: Session, gmp_record_id: int) -> int:
    last = (
        db.query(func.max(GMPApplicationLogs.del_index))
        .filter(GMPApplicationLogs.gmp_record_id == gmp_record_id)
        .scalar()
    )
    return last or 0


def get_logs_for_record(db: Session, gmp_record_id: int) -> List[GMPApplicationLogs]:
    """All logs for a record, ordered by del_index asc (IN PROGRESS always last)."""
    logs = (
        db.query(GMPApplicationLogs)
        .filter(GMPApplicationLogs.gmp_record_id == gmp_record_id)
        .order_by(GMPApplicationLogs.del_index.asc())
        .all()
    )
    # Sort so IN PROGRESS logs are at the end, matching Step3AppLogs behaviour
    in_progress = [l for l in logs if l.application_status == "IN PROGRESS"]
    completed   = [l for l in logs if l.application_status != "IN PROGRESS"]
    return completed + in_progress


def _assignee_match(username: Optional[str], user_id: Optional[int]):
    """A log belongs to this user if EITHER its stored user_id matches (stable
    across a username change) OR its user_name matches the current username
    (covers legacy / self-loop / deck / Excel-imported logs that never got a
    user_id). Kept as one helper so every task query stays in sync."""
    clauses = []
    if user_id is not None:
        clauses.append(GMPApplicationLogs.user_id == user_id)
    if username:
        clauses.append(GMPApplicationLogs.user_name == username)
    if not clauses:
        # No identity to match on — return a never-true clause.
        return GMPApplicationLogs.id.is_(None)
    return or_(*clauses)


def get_tasks_for_user(
    db: Session,
    username: str,
    application_step: Optional[str] = None,
    is_received: Optional[int] = None,
    page: int = 1,
    page_size: int = 10000,
    user_id: Optional[int] = None,
) -> Tuple[List[GMPApplicationLogs], int]:
    """
    Return all open tasks assigned to a user, joined with GMPRecord.
    Matched by user_id OR user_name (see _assignee_match).
    Defensively restricted to PRIMARY ('-01') reference numbers only —
    sibling issuance records (added via Add Issuance) should never carry
    their own application logs going forward (see add_gmp_issuance in
    gmp_record.py), but this guards against any legacy/orphaned logs from
    before that change so a DTN can never appear as more than one task.
    """
    query = (
        db.query(GMPApplicationLogs)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .options(joinedload(GMPApplicationLogs.gmp_record))
        .filter(
            _assignee_match(username, user_id),
            GMPApplicationLogs.del_thread == "Open",
            GMPApplicationLogs.del_last_index == 1,
            or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01")),
        )
    )
    if application_step:
        query = query.filter(GMPApplicationLogs.application_step == application_step)
    if is_received is not None:
        query = query.filter(GMPApplicationLogs.is_received == is_received)

    total = query.count()
    logs = (
        query.order_by(GMPApplicationLogs.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # A DTN can have multiple GMPRecord siblings (added via Add Issuance),
    # each with its own Type of Issuance, but only the primary ('-01') one
    # ever has a task/log. So the task's own embedded record only ever shows
    # one issuance type even when the DTN actually carries several. One bulk
    # query (indexed GMP_DTN, single IN clause) beats a per-row sibling
    # lookup — attach the result as a plain, non-persisted attribute so it
    # rides along through GMPTaskResponse's Pydantic serialization.
    dtns = {log.gmp_record.GMP_DTN for log in logs if log.gmp_record and log.gmp_record.GMP_DTN}
    issuance_by_dtn: Dict[int, List[str]] = {}
    if dtns:
        rows = (
            db.query(GMPRecord.GMP_DTN, GMPRecord.GMP_TYPE_OF_ISSUANCE)
            .filter(GMPRecord.GMP_DTN.in_(dtns), GMPRecord.GMP_TYPE_OF_ISSUANCE.isnot(None))
            .distinct()
            .all()
        )
        for dtn, issuance in rows:
            issuance_by_dtn.setdefault(dtn, []).append(issuance)
    for log in logs:
        dtn = log.gmp_record.GMP_DTN if log.gmp_record else None
        log.all_issuance_types = sorted(issuance_by_dtn.get(dtn, []))

    return logs, total

def get_task_counts_for_users(db: Session, usernames: List[str]) -> Dict[str, int]:
    """
    Same open-task criteria as get_task_count_for_user(), for a batch of
    usernames in one query — used by the Bulk Deck modal's evaluator checklist
    to show each evaluator's current workload without an N+1 request per name.
    Usernames with zero open tasks are simply absent from the returned dict.
    """
    if not usernames:
        return {}
    rows = (
        db.query(GMPApplicationLogs.user_name, func.count(GMPApplicationLogs.id))
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .filter(
            GMPApplicationLogs.user_name.in_(usernames),
            GMPApplicationLogs.del_thread == "Open",
            GMPApplicationLogs.del_last_index == 1,
            or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01")),
        )
        .group_by(GMPApplicationLogs.user_name)
        .all()
    )
    return {name: count for name, count in rows}


def get_task_count_for_user(db: Session, username: str, user_id: Optional[int] = None) -> int:
    """
    Count of open tasks currently assigned to a user, across every step.
    Matched by user_id OR user_name, same criteria as get_tasks_for_user, so a
    task drops out the moment it's decked/advanced/reassigned/rerouted
    (del_thread → "Close"). Same primary-only restriction.
    """
    return (
        db.query(GMPApplicationLogs)
        .join(GMPRecord, GMPApplicationLogs.gmp_record_id == GMPRecord.GMP_ID)
        .filter(
            _assignee_match(username, user_id),
            GMPApplicationLogs.del_thread == "Open",
            GMPApplicationLogs.del_last_index == 1,
            or_(GMPRecord.GMP_REFERENCE_NO.is_(None), GMPRecord.GMP_REFERENCE_NO.like("%-01")),
        )
        .count()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Update log (complete, add decision/remarks/doctrack)
# ─────────────────────────────────────────────────────────────────────────────

def update_log(
    db: Session,
    log_id: int,
    update_data: Dict[str, Any],
) -> Optional[GMPApplicationLogs]:
    """
    Patch any fields on an existing log.
    Used by the Step 4 action form to mark a log COMPLETED with decision details.
    """
    log = get_log_by_id(db, log_id)
    if not log:
        return None
    allowed = {
        "application_status", "application_decision", "application_remarks",
        "doctrack_remarks", "accomplished_date", "del_last_index", "del_thread",
        "action_type", "decision_result", "decision_authority_id",
        "decision_authority_name",
    }
    for field, value in update_data.items():
        if field in allowed:
            setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return log


# ─────────────────────────────────────────────────────────────────────────────
# Advance step
# ─────────────────────────────────────────────────────────────────────────────

def advance_step(
    db: Session,
    gmp_record_id: int,
    current_step: str,
    action: str,
    recommendation: str = "",
    remarks: str = "",
    next_assignee_name: Optional[str] = None,
    next_assignee_id: Optional[int] = None,
    next_step_label: Optional[str] = None,
    next_del_index: Optional[int] = None,
    performed_by_name: Optional[str] = None,
    performed_by_full_name: Optional[str] = None,
    performed_by_id: Optional[int] = None,
    performed_by_alias: Optional[str] = None,
    action_type: Optional[str] = None,
    decision_result: Optional[str] = None,
    decision_authority_id: Optional[int] = None,
    decision_authority_name: Optional[str] = None,
    doctrack_remarks: Optional[str] = None,
    deadline_date: Optional[datetime] = None,
    working_days: Optional[int] = None,
    completion_status: Optional[str] = None,
) -> Optional[GMPApplicationLogs]:
    """
    1. Find (or auto-create) the current OPEN log for current_step.
    2. Mark it COMPLETED with decision details.
    3. Create new IN PROGRESS log for next step (if next_step_label provided).
    Returns the new log (or the completed log if this is the final step).
    """
    now = _now()

    # Find current open log
    current_log = (
        db.query(GMPApplicationLogs)
        .filter(
            GMPApplicationLogs.gmp_record_id == gmp_record_id,
            GMPApplicationLogs.application_step == current_step,
            GMPApplicationLogs.del_thread == "Open",
        )
        .order_by(GMPApplicationLogs.del_index.desc())
        .first()
    )

    # ── Auto-create the initial log if none exists ────────────────────────────
    # This handles records uploaded via Excel that have no application logs yet.
    if not current_log:
        last_index = get_last_index(db, gmp_record_id)
        next_index = last_index + 1
        current_log = GMPApplicationLogs(
            gmp_record_id       = gmp_record_id,
            application_step    = current_step,
            application_status  = "IN PROGRESS",
            application_decision= "",
            application_remarks = "",
            start_date          = now,
            del_index           = next_index,
            del_previous        = last_index if last_index > 0 else None,
            del_last_index      = 1,
            del_thread          = "Open",
            user_name           = performed_by_name,
            user_id             = performed_by_id,
            is_received         = 0,
            is_starred          = 0,
            sent_by_user_id     = performed_by_id,
            sent_by_full_name   = performed_by_full_name,
            sent_by_user_name   = performed_by_name,
            sent_by_alias       = performed_by_alias,
        )
        db.add(current_log)
        db.commit()
        db.refresh(current_log)

    # Mark current log complete. Normally "COMPLETED" — pass completion_status
    # (e.g. "RELEASED") when the step's action means something more specific
    # than a generic hand-off, such as OD Releasing's final release action.
    current_log.application_status      = completion_status or "COMPLETED"
    current_log.application_decision    = action
    current_log.application_remarks     = remarks
    current_log.accomplished_date       = now
    current_log.del_thread              = "Close"
    current_log.del_last_index          = 0
    if action_type:
        current_log.action_type         = action_type
    if decision_result:
        current_log.decision_result     = decision_result
    if decision_authority_id:
        current_log.decision_authority_id   = decision_authority_id
    if decision_authority_name:
        current_log.decision_authority_name = decision_authority_name
    if doctrack_remarks:
        current_log.doctrack_remarks    = doctrack_remarks
    db.commit()
    db.refresh(current_log)

    if not next_step_label:
        # Final step — the workflow ends here (e.g. "Disapprove" at QA Admin /
        # LRD Chief Admin, per GMP_ACTION_ROUTES in gmp_record.py).
        # Clear the record's current step — it is no longer actively at any
        # step — and, for a Disapprove action specifically, mark the record
        # itself DISAPPROVED. Without this, GMP_CURRENT_STEP was left
        # pointing at the step the record was disapproved from forever,
        # which made it read as permanently "IN PROGRESS"/"on process" in
        # both the Queue Table (getEffectiveStatus()) and every GMP
        # analytics query that checks for an open current step. Other
        # terminal actions (e.g. OD Releasing's release) set GMP_APP_STATUS
        # themselves via a separate record update from the frontend (which
        # WorkflowModal issues right after this call), so we don't set it here.
        record = db.query(GMPRecord).filter(GMPRecord.GMP_ID == gmp_record_id).first()
        if record:
            record.GMP_CURRENT_STEP = None
            if action == "Disapprove":
                record.GMP_APP_STATUS = "DISAPPROVED"
            db.commit()
        return current_log

    # Get next del_index
    last_index = get_last_index(db, gmp_record_id)
    next_index = last_index + 1

    new_log = GMPApplicationLogs(
        gmp_record_id       = gmp_record_id,
        application_step    = next_step_label,
        application_status  = "IN PROGRESS",
        application_decision= "",
        application_remarks = "",
        start_date          = now,
        del_index           = next_index,
        del_previous        = current_log.del_index,
        del_last_index      = 1,
        del_thread          = "Open",
        user_name           = next_assignee_name,
        user_id             = next_assignee_id,
        is_received         = 1,
        is_starred          = 0,
        deadline_date       = deadline_date,
        working_days        = working_days,
        sent_by_user_id     = performed_by_id,
        sent_by_full_name   = performed_by_full_name,
        sent_by_user_name   = performed_by_name,
        sent_by_alias       = performed_by_alias,
    )
    db.add(new_log)

    # Update GMP_CURRENT_STEP on the parent record, and mirror it onto every
    # sibling reference number under the same DTN — only the primary ('-01')
    # reference has real application logs / a task, but every issuance
    # variant should visually progress in parallel with it.
    record = db.query(GMPRecord).filter(GMPRecord.GMP_ID == gmp_record_id).first()
    if record:
        record.GMP_CURRENT_STEP = next_step_label
        if record.GMP_DTN:
            db.query(GMPRecord).filter(
                GMPRecord.GMP_DTN == record.GMP_DTN,
                GMPRecord.GMP_ID != record.GMP_ID,
            ).update({"GMP_CURRENT_STEP": next_step_label}, synchronize_session=False)

    db.commit()
    db.refresh(new_log)

    dtn = get_gmp_dtn(db, gmp_record_id)
    _notify_gmp_assigned(db, new_log, dtn)

    return new_log


# ─────────────────────────────────────────────────────────────────────────────
# Reassign
# ─────────────────────────────────────────────────────────────────────────────

def reassign(
    db: Session,
    gmp_record_id: int,
    application_step: str,
    reassigned_by_user_name: Optional[str],
    reassigned_by_user_id: Optional[int],
    reassigned_to_user_name: str,
    reassigned_to_user_id: Optional[int] = None,
    reassignment_reason: Optional[str] = None,
    reassignment_remarks: Optional[str] = None,
    reassigned_by_alias: Optional[str] = None,
    reassigned_by_full_name: Optional[str] = None,
) -> Optional[GMPApplicationLogs]:
    """
    1. UPDATE current active log → COMPLETED + reassignment tracking fields.
    2. CREATE new IN PROGRESS log for new assignee at the same step.
    Returns the new log, or None if no open log found.
    """
    now = _now()

    # Find current open log for this step
    current_log = (
        db.query(GMPApplicationLogs)
        .filter(
            and_(
                GMPApplicationLogs.gmp_record_id == gmp_record_id,
                GMPApplicationLogs.application_status == "IN PROGRESS",
                GMPApplicationLogs.application_step == application_step,
            )
        )
        .order_by(GMPApplicationLogs.del_index.desc())
        .first()
    )

    if not current_log:
        return None

    # Store from-user before closing
    from_user_id   = current_log.user_id
    from_user_name = current_log.user_name

    # Close current log
    current_log.application_status      = "COMPLETED"
    current_log.del_last_index           = 0
    current_log.del_thread               = "Close"
    current_log.action_type              = "REASSIGNMENT"
    current_log.accomplished_date        = now
    current_log.reassigned_by_user_id    = reassigned_by_user_id
    current_log.reassigned_by_user_name  = reassigned_by_user_name
    current_log.reassigned_at            = now
    current_log.reassigned_from_user_id  = from_user_id
    current_log.reassigned_from_user_name= from_user_name
    current_log.reassigned_to_user_id    = reassigned_to_user_id
    current_log.reassigned_to_user_name  = reassigned_to_user_name
    current_log.reassignment_reason      = reassignment_reason
    current_log.reassignment_remarks     = reassignment_remarks
    
    db.commit()
    db.refresh(current_log)

    # Create new log for new assignee
    last_index = get_last_index(db, gmp_record_id)
    next_index = last_index + 1

    new_log = GMPApplicationLogs(
        gmp_record_id       = gmp_record_id,
        application_step    = application_step,
        application_status  = "IN PROGRESS",
        application_decision= "",
        application_remarks = "",
        start_date          = now,
        del_index           = next_index,
        del_previous        = current_log.del_index,
        del_last_index      = 1,
        del_thread          = "Open",
        user_name           = reassigned_to_user_name,
        user_id             = reassigned_to_user_id,
        is_received         = 1,
        is_starred          = 0,
        sent_by_user_id     = reassigned_by_user_id,
        sent_by_full_name   = reassigned_by_full_name,
        sent_by_user_name   = reassigned_by_user_name,
        sent_by_alias       = reassigned_by_alias,
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    dtn = get_gmp_dtn(db, gmp_record_id)
    _notify_gmp_assigned(db, new_log, dtn)

    return new_log


# ─────────────────────────────────────────────────────────────────────────────
# Reroute
# ─────────────────────────────────────────────────────────────────────────────

def reroute(
    db: Session,
    gmp_record_id: int,
    reroute_from_step: str,
    reroute_target_step: str,
    rerouted_by_user_name: Optional[str],
    rerouted_by_user_id: Optional[int],
    target_user_name: Optional[str] = None,
    target_user_id: Optional[int] = None,
    reroute_reason: Optional[str] = None,
    reroute_remarks: Optional[str] = None,
    rerouted_by_alias: Optional[str] = None,
    rerouted_by_full_name: Optional[str] = None,
) -> Optional[GMPApplicationLogs]:
    """
    1. UPDATE current active log → COMPLETED + reroute tracking fields.
    2. CREATE new IN PROGRESS log at the target step.
    Returns the new log, or None if no open log found.
    """
    now = _now()

    # Find current open log for the from-step
    current_log = (
        db.query(GMPApplicationLogs)
        .filter(
            and_(
                GMPApplicationLogs.gmp_record_id == gmp_record_id,
                GMPApplicationLogs.application_status == "IN PROGRESS",
                GMPApplicationLogs.application_step == reroute_from_step,
            )
        )
        .order_by(GMPApplicationLogs.del_index.desc())
        .first()
    )

    if not current_log:
        return None

    # Close current log
    current_log.application_status   = "COMPLETED"
    current_log.del_last_index        = 0
    current_log.del_thread            = "Close"
    current_log.action_type           = "REROUTE"
    current_log.accomplished_date     = now
    current_log.rerouted_by_user_id   = rerouted_by_user_id
    current_log.rerouted_by_user_name = rerouted_by_user_name
    current_log.rerouted_at           = now
    current_log.reroute_from_step     = reroute_from_step
    current_log.reroute_target_step   = reroute_target_step
    current_log.reroute_reason        = reroute_reason
    current_log.reroute_remarks       = reroute_remarks
    db.commit()
    db.refresh(current_log)

    # Create new log at target step
    last_index = get_last_index(db, gmp_record_id)
    next_index = last_index + 1

    new_log = GMPApplicationLogs(
        gmp_record_id       = gmp_record_id,
        application_step    = reroute_target_step,
        application_status  = "IN PROGRESS",
        application_decision= "",
        application_remarks = "",
        start_date          = now,
        del_index           = next_index,
        del_previous        = current_log.del_index,
        del_last_index      = 1,
        del_thread          = "Open",
        user_name           = target_user_name,
        user_id             = target_user_id,
        is_received         = 1,
        is_starred          = 0,
        sent_by_user_id     = rerouted_by_user_id,
        sent_by_full_name   = rerouted_by_full_name,
        sent_by_user_name   = rerouted_by_user_name,
        sent_by_alias       = rerouted_by_alias,
    )
    db.add(new_log)

    # Update GMP_CURRENT_STEP
    record = db.query(GMPRecord).filter(GMPRecord.GMP_ID == gmp_record_id).first()
    if record:
        record.GMP_CURRENT_STEP = reroute_target_step

    db.commit()
    db.refresh(new_log)

    dtn = get_gmp_dtn(db, gmp_record_id)
    _notify_gmp_assigned(db, new_log, dtn)

    return new_log


# ─────────────────────────────────────────────────────────────────────────────
# Mark received / toggle star
# ─────────────────────────────────────────────────────────────────────────────

def mark_received(
    db: Session, log_id: int, received_by_username: str
) -> Optional[GMPApplicationLogs]:
    log = get_log_by_id(db, log_id)
    if not log:
        return None
    log.is_received = 1
    log.received_at = _now()
    log.received_by = received_by_username
    db.commit()
    db.refresh(log)
    return log


def toggle_star(
    db: Session, log_id: int, star: bool
) -> Optional[GMPApplicationLogs]:
    log = get_log_by_id(db, log_id)
    if not log:
        return None
    log.is_starred = 1 if star else 0
    log.starred_at = _now() if star else None
    db.commit()
    db.refresh(log)
    return log
