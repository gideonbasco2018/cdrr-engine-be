"""
Authentication Schemas
Pydantic models for login, registration, and user responses
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from enum import Enum

# UserRole Enum for schemas
class UserRoleSchema(str, Enum):
    USER = "User"
    ADMIN = "Admin"
    SUPERADMIN = "SuperAdmin"


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=150)
    first_name: str = Field(..., min_length=1, max_length=100)
    surname: str = Field(..., min_length=1, max_length=100)
    position: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=100, description="Password must be at least 8 characters")
    role: Optional[UserRoleSchema] = UserRoleSchema.USER
    group_id: Optional[int] = Field(None, description="Group ID - defaults to 'Users' group if not provided")


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str
    password: str


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    surname: Optional[str] = Field(None, min_length=1, max_length=100)
    position: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = None
    group_id: Optional[int] = None  # Allow updating group


class UserResponse(UserBase):
    """Schema for user response"""
    id: int
    role: UserRoleSchema
    is_active: bool
    group_id: int  # Include group_id in response
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Schema for token payload data"""
    username: Optional[str] = None
    role: Optional[str] = None


class LoginResponse(BaseModel):
    """Schema for successful login response"""
    access_token: str
    token_type: str
    user: UserResponse  # This will now include role and group_id