from pydantic import BaseModel
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