"""
Schemas for Application Logs
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ApplicationLogBase(BaseModel):
    """Base schema for Application Log"""
    application_step: Optional[str] = Field(None, max_length=255, description="Step in application workflow (e.g., Decking, Evaluation, Checking)")
    user_name: Optional[str] = Field(None, max_length=255, description="Username of person performing action")
    application_status: Optional[str] = Field(None, max_length=255, description="Current status of application")
    application_decision: Optional[str] = Field(None, max_length=255, description="Decision made (e.g., Approved, For Checking)")
    application_remarks: Optional[str] = Field(None, description="Remarks or notes")
    start_date: Optional[datetime] = Field(None, description="When this step started")
    accomplished_date: Optional[datetime] = Field(None, description="When this step was completed")


class ApplicationLogCreate(ApplicationLogBase):
    """Schema for creating Application Log"""
    main_db_id: int = Field(..., description="ID of the main_db record (DB_ID)")


class ApplicationLogUpdate(ApplicationLogBase):
    """Schema for updating Application Log"""
    pass


class ApplicationLogResponse(ApplicationLogBase):
    """Schema for Application Log response"""
    id: int
    main_db_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True