# app/schemas/closed_tasks.py
"""
Schemas for Closed Tasks
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Shared base ───────────────────────────────────────────────────────
class ClosedTaskBase(BaseModel):
    reason_for_closing: str = Field(
        ...,
        max_length=255,
        description="Reason selected from dropdown (required)",
    )
    remarks: Optional[str] = Field(
        None,
        description="Additional closing remarks (optional)",
    )


# ── CREATE  (request body sent by the frontend) ───────────────────────
class ClosedTaskCreate(ClosedTaskBase):
    main_db_id: int = Field(
        ...,
        description="ID of the main_db record being closed",
    )
    app_log_id: Optional[int] = Field(
        None,
        description="ID of the IN PROGRESS application_log row (for audit trail)",
    )
    # Who closed the task — filled from the current logged-in user on the route layer
    closed_by_user_id: int = Field(
        ...,
        description="User ID of the person who performed the close action",
    )
    closed_by_user_name: str = Field(
        ...,
        max_length=255,
        description="Username of the person who performed the close action",
    )
    closed_at: Optional[datetime] = Field(
        None,
        description="Timestamp of the close action (defaults to server now() if omitted)",
    )


# ── BULK CREATE  (for closing multiple tasks at once) ─────────────────
class ClosedTaskBulkCreate(BaseModel):
    main_db_ids: List[int] = Field(
        ...,
        min_items=1,
        description="List of main_db IDs to close in one operation",
    )
    reason_for_closing: str = Field(..., max_length=255)
    remarks: Optional[str] = Field(None)
    closed_by_user_id: int = Field(...)
    closed_by_user_name: str = Field(..., max_length=255)
    closed_at: Optional[datetime] = Field(None)


# ── RESPONSE  (what the API returns) ─────────────────────────────────
class ClosedTaskResponse(ClosedTaskBase):
    id: int
    main_db_id: int
    app_log_id: Optional[int]
    closed_by_user_id: int
    closed_by_user_name: str
    closed_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Convenience: list response ────────────────────────────────────────
class ClosedTaskListResponse(BaseModel):
    total: int
    items: List[ClosedTaskResponse]