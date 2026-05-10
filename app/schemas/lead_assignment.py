# app/schemas/lead_assignment.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------------------
# Nested User Info
# ---------------------
class UserBrief(BaseModel):
    id: int
    username: str
    first_name: str
    surname: str
    position: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------
# Create
# ---------------------
class LeadAssignmentCreate(BaseModel):
    lead_user_id: int
    member_user_id: int
    lead_role: str                  # "Checker" or "Supervisor"
    remarks: Optional[str] = None


# ---------------------
# Update
# ---------------------
class LeadAssignmentUpdate(BaseModel):
    is_active: Optional[bool] = None
    remarks: Optional[str] = None


# ---------------------
# Single Response
# ---------------------
class LeadAssignmentResponse(BaseModel):
    id: int
    lead_user_id: int
    member_user_id: int
    lead_role: str
    is_active: bool
    remarks: Optional[str] = None
    assigned_at: datetime
    unassigned_at: Optional[datetime] = None
    assigned_by_user_id: Optional[int] = None

    # Nested user info
    lead: Optional[UserBrief] = None
    member: Optional[UserBrief] = None
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

class LeadAssignmentBatchCreate(BaseModel):
    lead_user_id:    int
    lead_role:       str          # "Checker" | "Supervisor"
    member_user_ids: List[int]    # maraming evaluators
    remarks:         Optional[str] = None