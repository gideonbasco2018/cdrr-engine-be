# FILE: app/schemas/clinical_trial_audit_log.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ClinicalTrialAuditLogOut(BaseModel):
    id: int
    clinical_trial_id: int
    action: str
    changed_fields: str
    old_values: str
    new_values: str
    changed_by: Optional[int] = None
    changed_by_name: Optional[str] = None  # resolved display name, not a DB column
    changed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
