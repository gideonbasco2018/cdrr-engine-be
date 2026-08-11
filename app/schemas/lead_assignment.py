# app/schemas/lead_assignment.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------------------
# Nested brief shapes
# ---------------------
class UserBrief(BaseModel):
    id: int
    username: str
    first_name: str
    surname: str
    position: Optional[str] = None

    class Config:
        from_attributes = True


class GroupBrief(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class UnitBrief(BaseModel):
    id: int
    name: str
    lead: Optional[UserBrief] = None
    qa_admin: Optional[UserBrief] = None

    class Config:
        from_attributes = True


# ---------------------
# Create
# ---------------------
class LeadAssignmentCreate(BaseModel):
    unit_id: int
    member_user_id: int
    group_id: int  # functional role within the unit
    remarks: Optional[str] = None


# ---------------------
# Update
# ---------------------
class LeadAssignmentUpdate(BaseModel):
    is_active: Optional[bool] = None
    remarks: Optional[str] = None
    group_id: Optional[int] = None  # re-tag role without recreating the row


# ---------------------
# Single Response
# ---------------------
class LeadAssignmentResponse(BaseModel):
    id: int
    unit_id: int
    member_user_id: int
    group_id: int
    is_active: bool
    remarks: Optional[str] = None
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None
    assigned_by_user_id: Optional[int] = None

    # Nested info
    unit: Optional[UnitBrief] = None
    member: Optional[UserBrief] = None
    group: Optional[GroupBrief] = None
    assigned_by: Optional[UserBrief] = None

    class Config:
        from_attributes = True


# ---------------------
# Paginated List Response
# ---------------------
class LeadAssignmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[LeadAssignmentResponse]


# ---------------------
# Batch create — one unit + one role, maraming members
# ---------------------
class LeadAssignmentBatchCreate(BaseModel):
    unit_id: int
    group_id: int  # same functional role for all members
    member_user_ids: List[int]
    remarks: Optional[str] = None
