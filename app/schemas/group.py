"""
schemas/group.py
Pydantic schemas for Group Management routes
"""
from typing import Optional, List
from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    user_count: Optional[int] = None  # dynamically computed sa route

    class Config:
        from_attributes = True  # SQLAlchemy model compat


class GroupUserAssign(BaseModel):
    user_id: int