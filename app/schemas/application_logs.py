"""
Schemas for Application Logs
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class ApplicationLogBase(BaseModel):
    application_step: Optional[str] = Field(None, max_length=255)
    user_name: Optional[str] = Field(None, max_length=255)
    application_status: Optional[str] = Field(None, max_length=255)
    application_decision: Optional[str] = Field(None, max_length=255)
    application_remarks: Optional[str] = Field(None)
    start_date: Optional[datetime] = Field(None)
    accomplished_date: Optional[datetime] = Field(None)
    del_index: Optional[int] = Field(None)
    del_previous: Optional[int] = Field(None)
    del_last_index: Optional[int] = Field(None)
    del_thread: Optional[str] = Field(None, max_length=60)
    deadline_date: Optional[date] = Field(None)
    working_days: Optional[int] = Field(None)

    # ── New action tracking fields ─────────────────────────────────
    user_id: Optional[int] = Field(None, description="ID of user who performed the action")
    action_type: Optional[str] = Field(None, max_length=100, description="Type of action performed")
    decision_result: Optional[str] = Field(None, max_length=255, description="Result of decision")
    decision_authority_id: Optional[int] = Field(None, description="ID of decision authority user")
    decision_authority_name: Optional[str] = Field(None, max_length=255, description="Name of decision authority")
    doctrack_remarks: Optional[str] = Field(None, description="Doctrack remarks for this log entry")
    
    # ── Received tracking fields ───────────────────────────────────
    is_received: Optional[int] = Field(None, description="0 = not received, 1 = received")
    received_at: Optional[datetime] = Field(None)
    received_by: Optional[str] = Field(None, max_length=255)


class ApplicationLogCreate(ApplicationLogBase):
    main_db_id: int = Field(..., description="ID of the main_db record (DB_ID)")


class ApplicationLogUpdate(ApplicationLogBase):
    pass


class ApplicationLogResponse(ApplicationLogBase):
    id: int
    main_db_id: int
    is_received: int = 0  # default value para hindi mag-error kung null
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True