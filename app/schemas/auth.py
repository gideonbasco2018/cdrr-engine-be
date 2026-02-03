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


# -----------------------------
# User creation schema
# -----------------------------
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, description="Password must be at least 8 characters")
    role: Optional[UserRoleSchema] = UserRoleSchema.USER
    group_id: Optional[int] = Field(None, description="Assign first group at creation")


# -----------------------------
# User update schema
# -----------------------------
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    surname: Optional[str] = Field(None, min_length=1, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
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
        if hasattr(user, 'groups') and user.groups:
            groups = [
                {"id": g.id, "name": g.name}
                for g in user.groups
            ]
        
        # Build response dict
        user_dict = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "surname": user.surname,
            "position": user.position,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
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