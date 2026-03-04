# app/schemas/notification.py

from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from typing import Optional


# ─────────────────────────────────────────────────────────────────────
# NOTIFICATION SCHEMAS
# ─────────────────────────────────────────────────────────────────────

class NotificationBase(BaseModel):
    user_name : str
    title     : str
    message   : str
    link_dtn  : Optional[str] = None
    app_log_id: Optional[int] = None


class NotificationCreate(NotificationBase):
    """Used internally by the cron job / system to create notifications."""
    pass


class NotificationOut(NotificationBase):
    id        : int
    is_read   : bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationUnreadCount(BaseModel):
    count: int


class MarkReadResponse(BaseModel):
    success: bool
    updated: int   # how many records were updated


# ─────────────────────────────────────────────────────────────────────
# APPLICATION LOGS — Deadline fields (extend your existing schema)
# ─────────────────────────────────────────────────────────────────────

class DeadlineFields(BaseModel):
    """Mixin — add to your existing ApplicationLogCreate schema."""
    deadline_date: Optional[date] = None
    working_days : Optional[int]  = None


# Example: if you have an existing ApplicationLogCreate schema, update it:
#
#   class ApplicationLogCreate(YourExistingBase, DeadlineFields):
#       pass
#
# Or just add the fields directly to your existing schema file.


class ApplicationLogDeadlineOut(BaseModel):
    """Lightweight response showing deadline info for a log."""
    id           : int
    user_name    : Optional[str]
    deadline_date: Optional[date]
    working_days : Optional[int]
    application_status  : Optional[str]
    application_decision: Optional[str]

    model_config = ConfigDict(from_attributes=True)