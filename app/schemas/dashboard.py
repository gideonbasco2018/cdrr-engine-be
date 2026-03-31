# app/schemas/dashboard.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class StatResponse(BaseModel):
    """Single KPI stat response."""
    label:     str            = Field(..., description="e.g. 'Total Received'")
    value:     int            = Field(..., description="Computed count")
    username:  str            = Field(..., description="Effective user this stat belongs to")
    date_from: Optional[date] = Field(None)
    date_to:   Optional[date] = Field(None)

    class Config:
        from_attributes = True


class CombinedStatsResponse(BaseModel):
    """All 3 KPI stats in one payload — used by /summary."""
    username:   str            = Field(..., description="Effective username")
    date_from:  Optional[date] = None
    date_to:    Optional[date] = None
    received:   int            = Field(..., description="Total applications received")
    completed:  int            = Field(..., description="application_status = COMPLETED")
    on_process: int            = Field(..., description="Still in-flight (not completed)")

    class Config:
        from_attributes = True