# app/schemas/field_audit_log.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# --- Per field change (isang row sa audit table) ---
class FieldChange(BaseModel):
    field_name:   str
    field_label:  Optional[str] = None
    old_value:    Optional[str] = None
    new_value:    Optional[str] = None
    step_context: Optional[str] = None


# --- Request body ng POST /field-audit-logs ---
class CreateFieldAuditLogRequest(BaseModel):
    main_db_id: int
    log_id:     Optional[int] = None
    session_id: str                    # UUID galing frontend
    changes:    List[FieldChange]      # lahat ng na-edit na fields


# --- Response per audit log row ---
class FieldAuditLogResponse(BaseModel):
    id:           int
    main_db_id:   int
    log_id:       Optional[int]
    changed_by:   str
    changed_at:   datetime
    field_name:   str
    field_label:  Optional[str]
    old_value:    Optional[str]
    new_value:    Optional[str]
    action_type:  str
    step_context: Optional[str]
    session_id:   Optional[str]

    class Config:
        from_attributes = True


# --- Response para sa GET (grouped by session) ---
class AuditSession(BaseModel):
    session_id:  str
    changed_by:  str
    changed_at:  datetime
    step_context: Optional[str]
    changes:     List[FieldAuditLogResponse]