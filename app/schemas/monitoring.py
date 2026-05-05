from pydantic import BaseModel, Field
from typing import Optional, List


class TaskStatusBreakdown(BaseModel):
    completed: int
    in_progress: int
    total: int


class UserTaskSummary(BaseModel):
    user_id: int
    username: str
    full_name: str
    position: Optional[str] = None
    group_name: Optional[str] = None
    role: str
    is_active: bool
    tasks: TaskStatusBreakdown

    class Config:
        orm_mode = True


class UsersTasksResponse(BaseModel):
    total_users: int
    data: List[UserTaskSummary]


class RecordItem(BaseModel):
    id: int
    dtn: Optional[str] = None
    user_name: Optional[str] = None
    drug_name: Optional[str] = None
    date_received_cent: Optional[str] = None
    timeline: Optional[str] = None
    app_step: Optional[str] = None
    app_status: Optional[str] = None
    prescription: Optional[str] = None

    class Config:
        orm_mode = True


class AllRecordsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[RecordItem]


# ── DTN date range filter schema (used internally / for OpenAPI docs) ──────────
# Both fields are 8-digit strings (YYYYMMDD).  The frontend always sends full
# 8-digit values by padding omitted month/day (From → 01/01, To → 12/31).
class DtnDateRangeFilter(BaseModel):
    dtn_date_from: Optional[str] = Field(
        None,
        min_length=8,
        max_length=8,
        description=(
            "Lower bound for DTN date range.  Must be YYYYMMDD (8 digits). "
            "Filters records where LEFT(dtn, 8) >= dtn_date_from."
        ),
        example="20230101",
    )
    dtn_date_to: Optional[str] = Field(
        None,
        min_length=8,
        max_length=8,
        description=(
            "Upper bound for DTN date range.  Must be YYYYMMDD (8 digits). "
            "Filters records where LEFT(dtn, 8) <= dtn_date_to."
        ),
        example="20261231",
    )