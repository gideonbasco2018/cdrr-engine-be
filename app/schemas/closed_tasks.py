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
        description="Additional closing remarks — pure user input lang, walang CPR notes dito",
    )
    date_released: Optional[datetime] = Field(
        None,
        description="Date the document was released",
    )
    type_doc_released: Optional[str] = Field(
        None,
        max_length=100,
        description="Type of document released (e.g. CPR, LOD, Certificate...)",
    )

    # ── CPR Verification Portal audit ────────────────────────────────
    cpr_api_enabled: Optional[bool] = Field(
        None,
        description="True = API was ON, False = API was OFF, None = not a CPR doc",
    )
    cpr_insert_success: Optional[bool] = Field(
        None,
        description="True = inserted OK, False = insert failed, None = not attempted",
    )
    cpr_insert_error: Optional[str] = Field(
        None,
        description="Error message kung nag-fail ang CPR insert",
    )
    cpr_skipped_by_user: bool = Field(
        False,
        description="True kung sinadyang i-OFF ng user ang CPR API toggle bago mag-close",
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
        min_length=1,
        description="List of main_db IDs to close in one operation",
    )
    reason_for_closing: str = Field(..., max_length=255)
    remarks: Optional[str] = Field(None)
    date_released: Optional[datetime] = Field(None)
    type_doc_released: Optional[str] = Field(None, max_length=100)
    closed_by_user_id: int = Field(...)
    closed_by_user_name: str = Field(..., max_length=255)
    closed_at: Optional[datetime] = Field(None)

    # ── CPR Verification Portal audit ────────────────────────────────
    cpr_api_enabled: Optional[bool] = Field(None)
    cpr_insert_success: Optional[bool] = Field(None)
    cpr_insert_error: Optional[str] = Field(None)
    cpr_skipped_by_user: bool = Field(False)


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