# app/crud/field_audit_log.py

from sqlalchemy.orm import Session
from collections import defaultdict
from typing import List, Optional

from app.models.field_audit_log import ApplicationFieldAuditLog
from app.schemas.field_audit_log import (
    CreateFieldAuditLogRequest,
    FieldAuditLogResponse,
    AuditSession,
    FieldChange,
)


# ---------------------------------------------------------------
# CREATE — I-bulk insert ang lahat ng field changes
# ---------------------------------------------------------------
def create_field_audit_logs(
    db:           Session,
    payload:      CreateFieldAuditLogRequest,
    changed_by:   str,
) -> dict:
    """
    I-loop ang bawat FieldChange sa payload,
    i-skip kung walang actual na pagbabago,
    then i-bulk insert lahat.
    """
    created_ids = []

    for change in payload.changes:
        # Skip kung pareho ang old at new value
        if str(change.old_value or "") == str(change.new_value or ""):
            continue

        log_entry = ApplicationFieldAuditLog(
            main_db_id   = payload.main_db_id,
            log_id       = payload.log_id,
            changed_by   = changed_by,
            field_name   = change.field_name,
            field_label  = change.field_label,
            old_value    = str(change.old_value) if change.old_value is not None else None,
            new_value    = str(change.new_value) if change.new_value is not None else None,
            action_type  = "UPDATE",
            step_context = change.step_context,
            session_id   = payload.session_id,
        )
        db.add(log_entry)
        db.flush()
        created_ids.append(log_entry.id)

    db.commit()

    return {
        "success":       True,
        "created_count": len(created_ids),
        "session_id":    payload.session_id,
        "ids":           created_ids,
    }


# ---------------------------------------------------------------
# READ — Kumuha ng audit history ng isang record (grouped by session)
# ---------------------------------------------------------------
def get_audit_history_by_record(
    db:         Session,
    main_db_id: int,
) -> List[AuditSession]:
    """
    I-fetch lahat ng audit logs ng isang main record,
    i-group by session_id para makita ang per-submit history.
    """
    logs = (
        db.query(ApplicationFieldAuditLog)
        .filter(ApplicationFieldAuditLog.main_db_id == main_db_id)
        .order_by(ApplicationFieldAuditLog.changed_at.desc())
        .all()
    )

    if not logs:
        return []

    sessions: dict      = defaultdict(list)
    session_meta: dict  = {}

    for log in logs:
        sid = log.session_id or str(log.id)
        sessions[sid].append(log)

        if sid not in session_meta:
            session_meta[sid] = {
                "session_id":   sid,
                "changed_by":   log.changed_by,
                "changed_at":   log.changed_at,
                "step_context": log.step_context,
            }

    result = []
    for sid, meta in session_meta.items():
        result.append(
            AuditSession(
                session_id   = meta["session_id"],
                changed_by   = meta["changed_by"],
                changed_at   = meta["changed_at"],
                step_context = meta["step_context"],
                changes      = [
                    FieldAuditLogResponse.model_validate(c)
                    for c in sessions[sid]
                ],
            )
        )

    return result


# ---------------------------------------------------------------
# READ — Kumuha ng lahat ng edits ng isang specific user
# ---------------------------------------------------------------
def get_audit_logs_by_user(
    db:       Session,
    username: str,
    limit:    int = 50,
) -> List[ApplicationFieldAuditLog]:
    """
    I-fetch lahat ng field changes na ginawa ng isang user.
    Useful para sa per-user activity report.
    """
    return (
        db.query(ApplicationFieldAuditLog)
        .filter(ApplicationFieldAuditLog.changed_by == username)
        .order_by(ApplicationFieldAuditLog.changed_at.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------
# READ — Single session details (para sa drill-down)
# ---------------------------------------------------------------
def get_audit_logs_by_session(
    db:         Session,
    session_id: str,
) -> List[ApplicationFieldAuditLog]:
    """
    I-fetch lahat ng field changes sa isang specific session_id.
    """
    return (
        db.query(ApplicationFieldAuditLog)
        .filter(ApplicationFieldAuditLog.session_id == session_id)
        .order_by(ApplicationFieldAuditLog.changed_at.asc())
        .all()
    )


# ---------------------------------------------------------------
# READ — Count ng changes per record (para sa summary/badge)
# ---------------------------------------------------------------
def get_audit_count_by_record(
    db:         Session,
    main_db_id: int,
) -> int:
    """
    Ilang beses na na-edit ang isang record.
    Pwedeng gamitin para sa badge/indicator sa UI.
    """
    return (
        db.query(ApplicationFieldAuditLog)
        .filter(ApplicationFieldAuditLog.main_db_id == main_db_id)
        .count()
    )