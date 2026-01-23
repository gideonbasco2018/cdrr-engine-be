# app/schemas/analytics.py
from pydantic import BaseModel
from typing import Optional, List

class ReceivedCount(BaseModel):
    source: str  # FDAC or CENTRAL
    count: int

class ReceivedAnalyticsResponse(BaseModel):
    year: int
    month: Optional[int] = None
    day: Optional[int] = None
    fdac: int
    central: int

    class Config:
        orm_mode = True


class MonthlyBreakdown(BaseModel):
    """Single month breakdown"""
    period: str  # e.g., "January" or "2024"
    month: Optional[int] = None  # 1-12 (only for monthly breakdown)
    year: int
    fdac: int
    central: int
    total: int


class ReceivedByPeriodResponse(BaseModel):
    """Response for bar graph data"""
    breakdown: str  # "month" or "year"
    year: Optional[int] = None  # Only for monthly breakdown
    data: List[MonthlyBreakdown]

    class Config:
        orm_mode = True