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
    # ── NEW: added so the Directors Diagram table can show Product Class
    #    (DB_PROD_CLASS_PRESCRIP) and Processing Type (DB_PROCESSING_TYPE).
    #    These were requested on the FE but were never wired up here, so
    #    the API silently omitted them (Pydantic just drops unknown attrs
    #    instead of erroring — that's why the columns rendered as "—"). ──
    prod_class_prescrip: Optional[str] = None
    processing_type: Optional[str] = None
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
    # ── Director's Target (separate from lead target above) ──────────
    is_directors_target: bool = False
    directors_target_start_date: Optional[date] = None
    directors_target_end_date: Optional[date] = None
    directors_target_remarks: Optional[str] = None


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lead_assignment_id: int
    member_user_id: int
    member_name: str
    lead_role: str
    unit_id: int
    unit_name: str
    assigned_at: Optional[datetime] = None
    task_count: int = 0
    target_count: int = 0


# ── "Every team" view (Monitoring) ───────────────────────────────────
class AllTeamsMemberOut(TeamMemberOut):
    lead_user_id: Optional[int] = None
    lead_name: str = ""
    directors_target_count: int = 0
    # Used for the PER-MEMBER badge — targets where this member
    # completed their own part (any step). See
    # count_member_directors_targets_completed.
    directors_target_completed_count: int = 0
    # Used for the TEAM/UNIT target total — targets where this member
    # completed SPECIFICALLY the Supervisor stage. See
    # count_member_directors_targets_supervisor_completed. Summed across
    # all members of a unit on the frontend to get the unit's total.
    directors_target_supervisor_completed_count: int = 0
    in_progress_count: int = 0


# ── Director's Target: system-wide, not lead-scoped ──────────────────
class DirectorsTargetCreate(BaseModel):
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


class DirectorsTargetBulkCreate(BaseModel):
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


class DirectorsTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_log_id: int
    main_db_id: int
    member_user_id: Optional[int] = None
    targeted_by_user_id: int
    is_active: bool
    remarks: Optional[str] = None
    target_start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    targeted_at: Optional[datetime] = None
    untargeted_at: Optional[datetime] = None


# ── Paginated in-progress-only task list ──────────────────────────
class MemberTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[MemberTaskOut]


class UnitSummaryItem(BaseModel):
    label: str
    count: int


class UnitInProgressSummary(BaseModel):
    by_step: List[UnitSummaryItem]
    by_app_type: List[UnitSummaryItem]
    by_product_class: List[UnitSummaryItem]
    by_processing_type: List[UnitSummaryItem]


class UnitTaskOut(MemberTaskOut):
    member_user_id: int
    member_name: str


class UnitTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[UnitTaskOut]


# ── Directors Monitoring — org-wide overview + detailed list ────────
class DirectorsTargetUnitSummary(BaseModel):
    unit_name: str
    total: int
    completed: int
    overdue: int
    on_track: int


class DirectorsTargetOverviewSummary(BaseModel):
    total: int
    completed: int
    overdue: int
    on_track: int
    by_unit: List[DirectorsTargetUnitSummary]


class DirectorsTargetDetailOut(BaseModel):
    target_id: int
    log_id: int
    dtn: Optional[int] = None
    brand_name: Optional[str] = None
    unit_name: str
    member_name: str
    current_step: Optional[str] = None
    current_status: Optional[str] = None
    target_start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    days_remaining: Optional[int] = None
    completion_status: str  # "completed" | "overdue" | "on_track"
    remarks: Optional[str] = None
    targeted_at: Optional[datetime] = None


class DirectorsTargetListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[DirectorsTargetDetailOut]
