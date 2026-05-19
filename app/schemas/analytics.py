# # app/schemas/analytics.py
# from pydantic import BaseModel
# from typing import Optional, List

# class ReceivedCount(BaseModel):
#     source: str  # FDAC or CENTRAL
#     count: int

# class ReceivedAnalyticsResponse(BaseModel):
#     year: int
#     month: Optional[int] = None
#     day: Optional[int] = None
#     fdac: int
#     central: int

#     class Config:
#         orm_mode = True


# class MonthlyBreakdown(BaseModel):
#     """Single month breakdown"""
#     period: str  # e.g., "January" or "2024"
#     month: Optional[int] = None  # 1-12 (only for monthly breakdown)
#     year: int
#     fdac: int
#     central: int
#     total: int


# class ReceivedByPeriodResponse(BaseModel):
#     """Response for bar graph data"""
#     breakdown: str  # "month" or "year"
#     year: Optional[int] = None  # Only for monthly breakdown
#     data: List[MonthlyBreakdown]

#     class Config:
#         orm_mode = True

# NEW/ 5-15

# app/schemas/analytics.py

from pydantic import BaseModel
from typing import Optional, List


class AnalyticsSummaryResponse(BaseModel):
    total: int
    cpr: int
    nod: int
    on_process: int
    completed: int
    approval_rate: float


class AnalyticsTrendItem(BaseModel):
    label: str
    cpr: int
    nod: int
    on_process: int
    completed: int

class AnalyticsTrendResponse(BaseModel):
    data: List[AnalyticsTrendItem]


class AnalyticsClassificationItem(BaseModel):
    type: str
    count: int
    cpr: int
    nod: int
    rate: float

class AnalyticsClassificationResponse(BaseModel):
    data: List[AnalyticsClassificationItem]


class AnalyticsYearItem(BaseModel):
    year: str
    total: int
    cpr: int
    nod: int
    on_process: int
    completed: int
    rate: float

class AnalyticsYearSummaryResponse(BaseModel):
    data: List[AnalyticsYearItem]


class AnalyticsDrugItem(BaseModel):
    name: str
    generic: Optional[str] = None
    rx: Optional[str] = None
    total: int
    cpr: int
    nod: int
    rate: float

class AnalyticsTopDrugsResponse(BaseModel):
    data: List[AnalyticsDrugItem]


class AnalyticsCountryItem(BaseModel):
    country: str
    count: int
    cpr: int
    nod: int
    on_process: int

class AnalyticsTopCountriesResponse(BaseModel):
    data: List[AnalyticsCountryItem]


class AnalyticsAvailableYearsResponse(BaseModel):
    years: List[str]