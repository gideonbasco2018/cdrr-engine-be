# FILE: app/crud/clinical_trial_audit_log.py
import json
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.clinical_trial_audit_log import ClinicalTrialAuditLog


def _serialize(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def create_audit_log(
    db: Session,
    clinical_trial_id: int,
    old_values: Dict[str, Any],
    new_values: Dict[str, Any],
    changed_by: Optional[int] = None,
    action: str = "UPDATE",
) -> ClinicalTrialAuditLog:
    changed_fields = {
        field: {
            "old": _serialize(old_values.get(field)),
            "new": _serialize(new_values.get(field)),
        }
        for field in new_values
        if old_values.get(field) != new_values.get(field)
    }

    log = ClinicalTrialAuditLog(
        clinical_trial_id=clinical_trial_id,
        action=action,
        changed_fields=json.dumps(changed_fields),
        old_values=json.dumps({k: _serialize(v) for k, v in old_values.items()}),
        new_values=json.dumps({k: _serialize(v) for k, v in new_values.items()}),
        changed_by=changed_by,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_logs_for_trial(
    db: Session, clinical_trial_id: int
) -> List[ClinicalTrialAuditLog]:
    """
    Returns audit logs for a trial with `changed_by_name` populated from the
    users table (falls back to "Unknown user" if the user record was
    deleted, and to None if the change was made by the system, i.e.
    changed_by is null).
    """
    from app.models.user import User  # local import to avoid a circular import

    logs = (
        db.query(ClinicalTrialAuditLog)
        .filter(ClinicalTrialAuditLog.clinical_trial_id == clinical_trial_id)
        .order_by(ClinicalTrialAuditLog.changed_at.desc())
        .all()
    )

    user_ids = {log.changed_by for log in logs if log.changed_by is not None}
    users_by_id = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_by_id = {
            user.id: (user.alias or f"{user.first_name} {user.surname}".strip())
            for user in users
        }

    for log in logs:
        if log.changed_by is None:
            log.changed_by_name = None
        else:
            log.changed_by_name = users_by_id.get(log.changed_by, "Unknown user")

    return logs
