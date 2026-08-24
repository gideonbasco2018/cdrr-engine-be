# app/schemas/gmp_analytics.py

from pydantic import BaseModel
from typing import Optional, List


class GMPAnalyticsAvailableYearsResponse(BaseModel):
    years: List[str]


class GMPAnalyticsSummaryResponse(BaseModel):
    total: int
    released: int
    on_process: int
    disapproved: int
    avg_tat_days: Optional[float] = None
    release_rate: float


class GMPAnalyticsIssuanceCountItem(BaseModel):
    label: str
    count: int

class GMPAnalyticsDTNSummaryResponse(BaseModel):
    total_dtns: int
    completed: int
    on_process: int
    disapproved: int
    multi_issuance_dtns: int
    issuance_count_distribution: List[GMPAnalyticsIssuanceCountItem]


class GMPAnalyticsTrendItem(BaseModel):
    label: str
    received: int
    released: int
    disapproved: int

class GMPAnalyticsTrendResponse(BaseModel):
    data: List[GMPAnalyticsTrendItem]


class GMPAnalyticsCategoryItem(BaseModel):
    name: str
    count: int

class GMPAnalyticsCategoryResponse(BaseModel):
    by_est_category: List[GMPAnalyticsCategoryItem]
    by_pics_nonpics: List[GMPAnalyticsCategoryItem]
    top_companies: List[GMPAnalyticsCategoryItem]
    by_issuance_type: List[GMPAnalyticsCategoryItem]
    by_transaction_type: List[GMPAnalyticsCategoryItem]
    by_product_line: List[GMPAnalyticsCategoryItem]


class GMPAnalyticsWorkloadItem(BaseModel):
    evaluator: str
    open_count: int
    avg_tat_days: Optional[float] = None

class GMPAnalyticsWorkloadResponse(BaseModel):
    data: List[GMPAnalyticsWorkloadItem]


class GMPAnalyticsAgingItem(BaseModel):
    label: str
    count: int

class GMPAnalyticsAgingResponse(BaseModel):
    data: List[GMPAnalyticsAgingItem]


class GMPAnalyticsNODDistributionItem(BaseModel):
    label: str
    count: int

class GMPAnalyticsNODResponse(BaseModel):
    total_records: int
    records_with_nod: int
    nod_rate: float
    avg_nod_count: float
    avg_compliance_turnaround_days: Optional[float] = None
    pending_compliance: int
    distribution: List[GMPAnalyticsNODDistributionItem]


class GMPAnalyticsPicsCountryItem(BaseModel):
    name: str
    count: int

class GMPAnalyticsPicsMismatchItem(BaseModel):
    gmp_id: int
    dtn: Optional[str] = None
    reference_no: Optional[str] = None
    company: Optional[str] = None
    foreign_manufacturer: Optional[str] = None
    declared: str
    detected_country: Optional[str] = None
    reason: str

class GMPAnalyticsPicsCountryResponse(BaseModel):
    by_country: List[GMPAnalyticsPicsCountryItem]
    mismatch_count: int
    mismatches: List[GMPAnalyticsPicsMismatchItem]


class GMPAnalyticsStepTimingItem(BaseModel):
    step: str
    total: int
    avg_days: Optional[float] = None
    min_days: Optional[int] = None
    max_days: Optional[int] = None

class GMPAnalyticsStepTimingResponse(BaseModel):
    data: List[GMPAnalyticsStepTimingItem]
