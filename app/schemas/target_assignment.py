# app/schemas/target_assignment.py

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator


# ── Request: mark/unmark a task as target ───────────────────────────
class TargetAssignmentCreate(BaseModel):
    application_log_id: int
    target_start_date: date
    target_end_date: date
    remarks: Optional[str] = None

    @field_validator("target_end_date")
    @classmethod
    def end_date_after_start(cls, v, info):
        start = info.data.get("target_start_date")
        if start and v < start:
            raise ValueError("target_end_date cannot be before target_start_date")
        return v


# ── Request: mark multiple tasks as target at once (same date range/remarks) ──
class TargetAssignmentBulkCreate(BaseModel):
    application_log_ids: List[int]
    target_start_date: date
    target_end_date: date
    remarks: Optional[str] = None

    @field_validator("application_log_ids")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("application_log_ids cannot be empty")
        return v

    @field_validator("target_end_date")
    @classmethod
    def end_date_after_start(cls, v, info):
        start = info.data.get("target_start_date")
        if start and v < start:
            raise ValueError("target_end_date cannot be before target_start_date")
        return v


class TargetAssignmentUpdate(BaseModel):
    is_active: bool
    target_start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    remarks: Optional[str] = None


# ── Response ─────────────────────────────────────────────────────────
class TargetAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_log_id: int
    main_db_id: int
    member_user_id: int
    lead_user_id: int
    lead_assignment_id: Optional[int] = None
    is_active: bool
    remarks: Optional[str] = None
    target_start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    targeted_at: Optional[datetime] = None
    untargeted_at: Optional[datetime] = None


# ── One entry in an application's step history (application_logs row) ──
class ApplicationHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: Optional[str] = None
    status: Optional[str] = None
    date: Optional[datetime] = None
    decision: Optional[str] = None
    user_name: Optional[str] = None


# ── Combined view for the "team + tasks" screen ─────────────────────
# One row = one application_logs task, flattened with brand/DTN info
# from main_db, plus whether it's currently targeted.
class MemberTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    db_id: int
    dtn: Optional[int] = None
    brand_name: Optional[str] = None
    step: Optional[str] = None
    status: Optional[str] = None
    entry_type: Optional[str] = None
    app_type: Optional[str] = None
    date_accomplished: Optional[datetime] = None
    date_received_center: Optional[str] = None
    is_targeted: bool = False
    target_assignment_id: Optional[int] = None
    target_start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    target_remarks: Optional[str] = None
    # Weighted per-stage checklist (see compute_application_progress in
    # crud/target_assignment.py for the exact stage weights/rules).
    application_progress_percent: Optional[float] = None
    application_history: List[ApplicationHistoryEntry] = []


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lead_assignment_id: int
    member_user_id: int
    member_name: str
    lead_role: str
    assigned_at: Optional[datetime] = None
    task_count: int = 0
    target_count: int = 0


# ── "Every team" view (Monitoring) ───────────────────────────────────
# Same shape as TeamMemberOut, plus which lead this member reports to —
# used when an admin browses ALL teams instead of just "my team".
class AllTeamsMemberOut(TeamMemberOut):
    lead_user_id: int
    lead_name: str
