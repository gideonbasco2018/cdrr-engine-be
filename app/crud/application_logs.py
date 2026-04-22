# app/crud/application_logs.py
"""
CRUD Operations for Application Logs
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime

from app.models.application_logs import ApplicationLogs
from app.schemas.application_logs import ApplicationLogCreate, ApplicationLogUpdate
from app.crud.notification import create_notification, already_notified_today
from app.schemas.notification import NotificationCreate


# ─────────────────────────────────────────────────────────────────────
# NOTIFICATION HELPERS
# ─────────────────────────────────────────────────────────────────────

_ASSIGNED_TITLES = {
    "S&E"               : "📋 New S&E Task Assigned",
    "Quality Evaluation": "🔬 New Quality Evaluation Task Assigned",
    "Decking"           : "🎯 Application Decked",
}

_ASSIGNED_MESSAGES = {
    "S&E"               : "You have been assigned an S&E task for DTN: {dtn}. Please review and process accordingly.",
    "Quality Evaluation": "You have been assigned a Quality Evaluation task for DTN: {dtn}. Please review and process accordingly.",
    "Decking"           : "DTN {dtn} has been decked and assigned to you for processing.",
}

_COMPLETED_TITLES = {
    "S&E"               : "✅ S&E Task Completed",
    "Quality Evaluation": "✅ Quality Evaluation Completed",
    "Decking"           : "✅ Decking Completed",
}


def _get_dtn(db: Session, main_db_id: int) -> str:
    """
    Fetch the DTN string from the main_db table.
    Falls back to the raw ID string if the record is not found.
    Adjust the import + model name to match your actual MainDB model.
    """
    try:
        from app.models.main_db import MainDB
        main = db.query(MainDB).filter(MainDB.DB_ID == main_db_id).first()
        if main and getattr(main, "DB_DTN", None):
            return str(main.DB_DTN)
    except Exception:
        pass
    return str(main_db_id)


def _notify_assigned_user(db: Session, log_obj: ApplicationLogs, dtn: str) -> None:
    """
    Create a notification for the user who was just assigned an IN PROGRESS task.
    Silently skips on any error so it never breaks the main flow.
    """
    try:
        if log_obj.application_status != "IN PROGRESS":
            return
        if not log_obj.user_name:
            return

        step  = log_obj.application_step or ""
        title = _ASSIGNED_TITLES.get(step, f"📌 New Task: {step}")
        msg   = _ASSIGNED_MESSAGES.get(
            step,
            f"You have a new task for DTN: {dtn}.",
        ).format(dtn=dtn)

        # Duplicate guard — one notification per user + DTN + step per day
        if already_notified_today(db, log_obj.user_name, dtn, title_like=step):
            return

        create_notification(db, NotificationCreate(
            user_name  = log_obj.user_name,
            title      = title,
            message    = msg,
            link_dtn   = dtn,
            app_log_id = log_obj.id,
        ))
    except Exception:
        pass  # notification failure must never crash the main operation


def _notify_on_complete(
    db             : Session,
    log_obj        : ApplicationLogs,
    dtn            : str,
    notify_username: str,
) -> None:
    """
    Notify a supervisor / decker when a step is marked COMPLETED.
    `notify_username` = the person who should receive the notification
                        (e.g. the decker, or a supervisor account).
    Silently skips on any error.
    """
    try:
        if log_obj.application_status != "COMPLETED":
            return
        if not notify_username:
            return

        step  = log_obj.application_step or ""
        title = _COMPLETED_TITLES.get(step, f"✅ {step} Completed")
        msg   = (
            f"{log_obj.user_name} has completed the {step} step "
            f"for DTN: {dtn}."
        )

        if already_notified_today(db, notify_username, dtn, title_like="Completed"):
            return

        create_notification(db, NotificationCreate(
            user_name  = notify_username,
            title      = title,
            message    = msg,
            link_dtn   = dtn,
            app_log_id = log_obj.id,
        ))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────────────────────────────
def create(db: Session, log_in: ApplicationLogCreate) -> ApplicationLogs:
    db_log = ApplicationLogs(
        main_db_id              = log_in.main_db_id,
        application_step        = log_in.application_step,
        user_name               = log_in.user_name,
        application_status      = log_in.application_status,
        application_decision    = log_in.application_decision,
        application_remarks     = log_in.application_remarks,
        start_date              = log_in.start_date,
        accomplished_date       = log_in.accomplished_date,
        del_index               = log_in.del_index,
        del_previous            = log_in.del_previous,
        del_last_index          = log_in.del_last_index,
        del_thread              = log_in.del_thread,
        deadline_date           = log_in.deadline_date,
        working_days            = log_in.working_days,
        # ── Existing new fields ────────────────────────────────────
        user_id                 = log_in.user_id,
        action_type             = log_in.action_type,
        decision_result         = log_in.decision_result,
        decision_authority_id   = log_in.decision_authority_id,
        decision_authority_name = log_in.decision_authority_name,
        doctrack_remarks        = log_in.doctrack_remarks,
        is_received             = log_in.is_received or 0,
        received_at             = log_in.received_at,
        received_by             = log_in.received_by,
        # ── Re-assignment fields ───────────────────────────────────
        reassigned_by_user_id   = log_in.reassigned_by_user_id,
        reassigned_by_user_name = log_in.reassigned_by_user_name,
        reassigned_at           = log_in.reassigned_at,
        reassigned_from_user_id = log_in.reassigned_from_user_id,
        reassigned_from_user_name = log_in.reassigned_from_user_name,
        reassigned_to_user_id   = log_in.reassigned_to_user_id,
        reassigned_to_user_name = log_in.reassigned_to_user_name,
        reassignment_reason     = log_in.reassignment_reason,
        reassignment_remarks    = log_in.reassignment_remarks,
        # ── Re-route fields ───────────────────────────────────────
        rerouted_by_user_id     = log_in.rerouted_by_user_id,
        rerouted_by_user_name   = log_in.rerouted_by_user_name,
        rerouted_at             = log_in.rerouted_at,
        reroute_from_step       = log_in.reroute_from_step,
        reroute_target_step     = log_in.reroute_target_step,
        reroute_reason          = log_in.reroute_reason,
        reroute_remarks         = log_in.reroute_remarks,
    )

    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    dtn = _get_dtn(db, db_log.main_db_id)
    _notify_assigned_user(db, db_log, dtn)

    return db_log


def create_bulk(db: Session, logs_in: List[ApplicationLogCreate]) -> List[ApplicationLogs]:
    try:
        db_logs = []

        for log_in in logs_in:
            db_log = ApplicationLogs(
                main_db_id              = log_in.main_db_id,
                application_step        = log_in.application_step,
                user_name               = log_in.user_name,
                application_status      = log_in.application_status,
                application_decision    = log_in.application_decision,
                application_remarks     = log_in.application_remarks,
                start_date              = log_in.start_date,
                accomplished_date       = log_in.accomplished_date,
                del_index               = log_in.del_index,
                del_previous            = log_in.del_previous,
                del_last_index          = log_in.del_last_index,
                del_thread              = log_in.del_thread,
                deadline_date           = log_in.deadline_date,
                working_days            = log_in.working_days,
                # ── New fields ─────────────────────────────────────
                user_id                 = log_in.user_id,
                action_type             = log_in.action_type,
                decision_result         = log_in.decision_result,
                decision_authority_id   = log_in.decision_authority_id,
                decision_authority_name = log_in.decision_authority_name,
                is_received             = log_in.is_received or 0,
                received_at             = log_in.received_at,
                received_by             = log_in.received_by,
            )
            db.add(db_log)
            db_logs.append(db_log)

        db.commit()

        for db_log in db_logs:
            db.refresh(db_log)

        for db_log in db_logs:
            dtn = _get_dtn(db, db_log.main_db_id)
            _notify_assigned_user(db, db_log, dtn)

        return db_logs

    except Exception as e:
        db.rollback()
        raise e


# ─────────────────────────────────────────────────────────────────────
# READ
# ─────────────────────────────────────────────────────────────────────

def get_by_id(db: Session, log_id: int) -> Optional[ApplicationLogs]:
    """Get application log by ID"""
    return db.query(ApplicationLogs).filter(ApplicationLogs.id == log_id).first()


def get_by_main_db_id(db: Session, main_db_id: int) -> List[ApplicationLogs]:
    """
    Get all logs for a specific main_db record.
    Returns logs ordered by created_at (newest first).
    """
    return (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.main_db_id == main_db_id)
        .order_by(ApplicationLogs.created_at.desc())
        .all()
    )


def get_by_step(db: Session, main_db_id: int, step: str) -> List[ApplicationLogs]:
    """Get logs for a specific step (e.g., 'Decking', 'Evaluation')"""
    return (
        db.query(ApplicationLogs)
        .filter(
            ApplicationLogs.main_db_id == main_db_id,
            ApplicationLogs.application_step == step,
        )
        .order_by(ApplicationLogs.created_at.desc())
        .all()
    )


def get_all_by_step(db: Session, step: str, limit: int = 100) -> List[ApplicationLogs]:
    """
    Get all logs for a specific step across all applications.
    Useful for reporting / analytics.
    """
    return (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.application_step == step)
        .order_by(ApplicationLogs.created_at.desc())
        .limit(limit)
        .all()
    )


def get_by_user(db: Session, user_name: str, limit: int = 100) -> List[ApplicationLogs]:
    """
    Get all logs for a specific user.
    Useful for tracking user activity.
    """
    return (
        db.query(ApplicationLogs)
        .filter(ApplicationLogs.user_name == user_name)
        .order_by(ApplicationLogs.created_at.desc())
        .limit(limit)
        .all()
    )


def get_by_date_range(
    db        : Session,
    start_date: datetime,
    end_date  : datetime,
    step      : Optional[str] = None,
) -> List[ApplicationLogs]:
    """
    Get logs within a date range.
    Useful for reporting and analytics.
    """
    query = db.query(ApplicationLogs).filter(
        ApplicationLogs.created_at >= start_date,
        ApplicationLogs.created_at <= end_date,
    )

    if step:
        query = query.filter(ApplicationLogs.application_step == step)

    return query.order_by(ApplicationLogs.created_at.desc()).all()


# ─────────────────────────────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────────────────────────────

def update(db: Session, log_id: int, log_in: ApplicationLogUpdate) -> Optional[ApplicationLogs]:
    """
    Update an application log.
    If the status changes to COMPLETED, a notification is sent to the
    decker (del_previous log's user) so they know the step is done.
    """
    db_log = get_by_id(db, log_id)
    if not db_log:
        return None

    old_status = db_log.application_status
    update_data = log_in.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_log, field, value)

    db.commit()
    db.refresh(db_log)

    # ── Notify on COMPLETED transition ────────────────────────────────
    new_status = db_log.application_status
    if old_status != "COMPLETED" and new_status == "COMPLETED":
        try:
            dtn = _get_dtn(db, db_log.main_db_id)

            # Find the decker (the log right before this one) to notify
            prev_log = (
                db.query(ApplicationLogs)
                .filter(
                    ApplicationLogs.main_db_id == db_log.main_db_id,
                    ApplicationLogs.del_index  == db_log.del_previous,
                )
                .first()
            )
            supervisor = prev_log.user_name if prev_log else None
            _notify_on_complete(db, db_log, dtn, notify_username=supervisor)
        except Exception:
            pass

    return db_log


# ─────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────

def delete(db: Session, log_id: int) -> bool:
    """Delete an application log"""
    db_log = get_by_id(db, log_id)
    if not db_log:
        return False

    db.delete(db_log)
    db.commit()

    return True


def delete_bulk(db: Session, log_ids: List[int]) -> int:
    """
    Delete multiple application logs.

    Args:
        db: Database session
        log_ids: List of log IDs to delete

    Returns:
        Number of logs deleted
    """
    try:
        deleted_count = (
            db.query(ApplicationLogs)
            .filter(ApplicationLogs.id.in_(log_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        return deleted_count

    except Exception as e:
        db.rollback()
        raise e


# ─────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────

def get_last_index(db: Session, main_db_id: int) -> int:
    """
    Get the highest del_index for a specific application.
    Returns 0 if no logs exist yet.
    """
    last_index = (
        db.query(func.max(ApplicationLogs.del_index))
        .filter(ApplicationLogs.main_db_id == main_db_id)
        .scalar()
    )
    return last_index or 0


def reassign(db: Session, log_in: ApplicationLogCreate) -> ApplicationLogs:
    """
    Re-assignment flow:
    1. UPDATE current active log → COMPLETED + re-assignment fields
    2. CREATE new log → IN PROGRESS for new assignee
    """
    from sqlalchemy import and_

    # ── STEP 1: Find and UPDATE the current active log ─────────────────
    current_log = (
        db.query(ApplicationLogs)
        .filter(
            and_(
                ApplicationLogs.main_db_id == log_in.main_db_id,
                ApplicationLogs.application_status == "IN PROGRESS",
                ApplicationLogs.application_step == log_in.application_step,
            )
        )
        .order_by(ApplicationLogs.del_index.desc())
        .first()
    )

    if current_log:
        current_log.application_status  = "COMPLETED"
        current_log.del_last_index       = 0
        current_log.del_thread           = "Close"
        current_log.action_type          = "REASSIGNMENT"
        current_log.accomplished_date    = log_in.reassigned_at or func.now()
        # ── Re-assignment tracking ──
        current_log.reassigned_by_user_id   = log_in.reassigned_by_user_id
        current_log.reassigned_by_user_name = log_in.reassigned_by_user_name
        current_log.reassigned_at           = log_in.reassigned_at
        current_log.reassigned_from_user_id   = current_log.user_id   
        current_log.reassigned_from_user_name = current_log.user_name  
        current_log.reassigned_to_user_id   = log_in.reassigned_to_user_id
        current_log.reassigned_to_user_name = log_in.reassigned_to_user_name
        current_log.reassignment_reason     = log_in.reassignment_reason
        current_log.reassignment_remarks    = log_in.reassignment_remarks
        db.commit()
        db.refresh(current_log)

    # ── STEP 2: Get next del_index ──────────────────────────────────────
    last_index = get_last_index(db, log_in.main_db_id)
    next_index = last_index + 1

    # ── STEP 3: CREATE new log for new assignee ─────────────────────────
    new_log = ApplicationLogs(
        main_db_id           = log_in.main_db_id,
        application_step     = log_in.application_step,
        application_status   = "IN PROGRESS",
        application_decision = log_in.application_decision,
        application_remarks  = log_in.application_remarks,
        del_index            = next_index,
        del_previous         = last_index,
        del_last_index       = 1,
        del_thread           = "Open",
        start_date           = log_in.reassigned_at or func.now(),
        # ── New assignee ──
        user_name            = log_in.reassigned_to_user_name,
        user_id              = log_in.reassigned_to_user_id,
    )

    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    dtn = _get_dtn(db, new_log.main_db_id)
    _notify_assigned_user(db, new_log, dtn)

    return new_log


def reroute(db: Session, log_in: ApplicationLogCreate) -> ApplicationLogs:
    """
    Re-route flow:
    1. UPDATE current active log → COMPLETED + re-route fields
    2. CREATE new log → IN PROGRESS for target step
    """
    from sqlalchemy import and_

    # ── STEP 1: Find and UPDATE the current active log ─────────────────
    current_log = (
        db.query(ApplicationLogs)
        .filter(
            and_(
                ApplicationLogs.main_db_id == log_in.main_db_id,
                ApplicationLogs.application_status == "IN PROGRESS",
                ApplicationLogs.application_step == log_in.reroute_from_step,
            )
        )
        .order_by(ApplicationLogs.del_index.desc())
        .first()
    )

    if current_log:
        current_log.application_status  = "COMPLETED"
        current_log.del_last_index       = 0
        current_log.del_thread           = "Close"
        current_log.action_type          = "REROUTE"
        current_log.accomplished_date    = log_in.rerouted_at or func.now()
        # ── Re-route tracking ──
        current_log.rerouted_by_user_id   = log_in.rerouted_by_user_id
        current_log.rerouted_by_user_name = log_in.rerouted_by_user_name
        current_log.rerouted_at           = log_in.rerouted_at
        current_log.reroute_from_step     = log_in.reroute_from_step
        current_log.reroute_target_step   = log_in.reroute_target_step
        current_log.reroute_reason        = log_in.reroute_reason
        current_log.reroute_remarks       = log_in.reroute_remarks
        db.commit()
        db.refresh(current_log)

    # ── STEP 2: Get next del_index ──────────────────────────────────────
    last_index = get_last_index(db, log_in.main_db_id)
    next_index = last_index + 1

    # ── STEP 3: CREATE new log for target step ──────────────────────────
    new_log = ApplicationLogs(
        main_db_id           = log_in.main_db_id,
        application_step     = log_in.reroute_target_step,
        application_status   = "IN PROGRESS",
        application_decision = log_in.application_decision,
        application_remarks  = log_in.application_remarks,
        del_index            = next_index,
        del_previous         = last_index,
        del_last_index       = 1,
        del_thread           = "Open",
        start_date           = log_in.rerouted_at or func.now(),
        # ── Assigned user sa target step ──
        user_name            = log_in.user_name,
        user_id              = log_in.user_id,
    )

    db.add(new_log)
    db.commit()
    db.refresh(new_log)

    dtn = _get_dtn(db, new_log.main_db_id)
    _notify_assigned_user(db, new_log, dtn)

    return new_log