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
    return (
        db.query(ClinicalTrialAuditLog)
        .filter(ClinicalTrialAuditLog.clinical_trial_id == clinical_trial_id)
        .order_by(ClinicalTrialAuditLog.changed_at.desc())
        .all()
    )
