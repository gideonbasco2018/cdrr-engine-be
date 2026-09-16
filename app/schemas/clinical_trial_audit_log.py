# FILE: app/schemas/clinical_trial_audit_log.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ClinicalTrialAuditLogOut(BaseModel):
    id: int
    clinical_trial_id: int
    action: str
    changed_fields: Optional[str] = None
    old_values: Optional[str] = None
    new_values: Optional[str] = None
    changed_by: Optional[int] = None
    changed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
