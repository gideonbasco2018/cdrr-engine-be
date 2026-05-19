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


class AnalyticsFRPTATItem(BaseModel):
    quarter: str
    total_applications: int
    avg_tat_days: Optional[float] = None
    min_tat_days: Optional[int] = None
    max_tat_days: Optional[int] = None
    target_days:  Optional[int]   = None

class AnalyticsFRPTATResponse(BaseModel):
    data: List[AnalyticsFRPTATItem]