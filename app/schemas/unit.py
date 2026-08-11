# app/schemas/unit.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class UserBrief(BaseModel):
    id: int
    username: str
    first_name: str
    surname: str
    position: Optional[str] = None

    class Config:
        from_attributes = True


class UnitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    lead_user_id: Optional[int] = None
    qa_admin_user_id: Optional[int] = None


class UnitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    lead_user_id: Optional[int] = None
    qa_admin_user_id: Optional[int] = None
    is_active: Optional[bool] = None


class UnitResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    lead: Optional[UserBrief] = None
    qa_admin: Optional[UserBrief] = None
    member_count: int = 0

    class Config:
        from_attributes = True


class UnitListResponse(BaseModel):
    total: int
    data: List[UnitResponse]
