"""
Authentication Schemas - UPDATED & SIMPLIFIED
Pydantic models for login, registration, and user responses
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


# -----------------------------
# UserRole Enum for schemas
# -----------------------------
class UserRoleSchema(str, Enum):
    USER = "User"
    ADMIN = "Admin"
    SUPERADMIN = "SuperAdmin"


# -----------------------------
# Base user schema
# -----------------------------
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=150)
    first_name: str = Field(..., min_length=1, max_length=100)
    surname: str = Field(..., min_length=1, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    alias: Optional[str] = Field(None, max_length=100)


# -----------------------------
# User creation schema
# -----------------------------
class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password must be at least 8 characters",
    )
    role: Optional[UserRoleSchema] = UserRoleSchema.USER
    group_id: Optional[int] = Field(None, description="Assign first group at creation")
    access_request: Optional[str] = Field(None, max_length=1000)


# -----------------------------
# User update schema
# -----------------------------
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    surname: Optional[str] = Field(None, min_length=1, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    alias: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = None
    group_id: Optional[int] = None


# -----------------------------
# Group info schema
# -----------------------------
class GroupInfo(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# -----------------------------
# User response schema - WITH GROUP NAMES
# -----------------------------
class UserResponse(UserBase):
    id: int
    role: UserRoleSchema
    is_active: bool
    created_at: datetime
    updated_at: datetime

    access_request: Optional[str] = None
    profile_picture_url: Optional[str] = None
    # ✅ Array of groups with ID and name
    groups: List[GroupInfo] = []

    class Config:
        from_attributes = True

    @staticmethod
    def model_validate(user, **kwargs):
        """
        Custom validation to extract groups from SQLAlchemy relationship
        """
        # Extract groups (id and name) from user.groups relationship
        groups = []
        if hasattr(user, "groups") and user.groups:
            groups = [{"id": g.id, "name": g.name} for g in user.groups]

        # Build response dict
        user_dict = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "alias": getattr(user, "alias", None),
            "first_name": user.first_name,
            "surname": user.surname,
            "position": user.position,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "access_request": getattr(user, "access_request", None),
            "profile_picture_url": getattr(user, "profile_picture_url", None),
            "groups": groups,
        }

        return BaseModel.model_validate(UserResponse, user_dict)


# -----------------------------
# JWT token schemas
# -----------------------------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class AdminUserUpdate(BaseModel):
    """Schema for admin updating another user's details"""

    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None  # "User", "Admin", or "SuperAdmin"
    first_name: Optional[str] = None
    surname: Optional[str] = None
    position: Optional[str] = None
    alias: Optional[str] = None
    group_id: Optional[int] = None
    access_request: Optional[str] = None
