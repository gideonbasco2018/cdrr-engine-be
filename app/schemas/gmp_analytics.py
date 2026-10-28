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
    on_process: int = 0

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


class GMPAnalyticsByStepItem(BaseModel):
    step: str
    count: int

class GMPAnalyticsByStepResponse(BaseModel):
    data: List[GMPAnalyticsByStepItem]


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
    pics: bool = False  # the country is a current PIC/S member

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
    avg_minutes: Optional[float] = None
    min_minutes: Optional[int] = None
    max_minutes: Optional[int] = None

class GMPAnalyticsStepTimingResponse(BaseModel):
    data: List[GMPAnalyticsStepTimingItem]


class GMPAnalyticsMonthlyItem(BaseModel):
    period: str
    label: str
    received: int
    released: int
    disapproved: int
    on_process: int
    release_rate: float
    released_in_month: int
    avg_tat_days: Optional[float] = None

class GMPAnalyticsMonthlyResponse(BaseModel):
    data: List[GMPAnalyticsMonthlyItem]


class GMPAnalyticsSparkPoint(BaseModel):
    date: Optional[str] = None  # ISO day, e.g. "2026-09-14"
    label: str
    received: int
    released: int
    disapproved: int
    on_process: int
    avg_tat_days: Optional[float] = None

class GMPAnalyticsSparklinesResponse(BaseModel):
    granularity: str  # "month" or "day"
    points: List[GMPAnalyticsSparkPoint]


class GMPAnalyticsDataQualityItem(BaseModel):
    year: str
    total: int
    received_filled: int
    missing_received: int
    release_expected: int
    released_filled: int
    missing_released: int
    doc_expected: int
    doc_filled: int
    missing_doc: int
    complete: int
    incomplete: int
    completeness: float

class GMPAnalyticsDataQualityResponse(BaseModel):
    data: List[GMPAnalyticsDataQualityItem]


class GMPAnalyticsQualityRecord(BaseModel):
    gmp_id: int
    dtn: Optional[str] = None
    reference_no: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None
    current_step: Optional[str] = None
    date_received: Optional[str] = None
    released_date: Optional[str] = None
    type_of_issuance: Optional[str] = None
    missing: List[str] = []

class GMPAnalyticsQualityRecordsResponse(BaseModel):
    data: List[GMPAnalyticsQualityRecord]
    total: int
    page: int
    total_pages: int
