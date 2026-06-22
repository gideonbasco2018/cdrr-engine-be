# app/schemas/frp_monitoring.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List

FRP_TYPE = "FRP and CRP"


# ── KPI Summary ───────────────────────────────────────────────────────────────
class FRPKpiSummaryResponse(BaseModel):
    total_applications: int
    cpr_released: int
    lod_released: int
    on_process: int
    released_this_month: int
    pending: int
    overdue: int


# ── Status Distribution ───────────────────────────────────────────────────────
class StatusCount(BaseModel):
    status: str
    count: int


class FRPStatusDistributionResponse(BaseModel):
    total: int
    data: List[StatusCount]


# ── Doc Types ─────────────────────────────────────────────────────────────────
class DocTypeCount(BaseModel):
    doc_type: str
    count: int


class FRPDocTypesResponse(BaseModel):
    total: int
    data: List[DocTypeCount]


# ── Top Countries ─────────────────────────────────────────────────────────────
class CountryCount(BaseModel):
    country: str
    total: int
    approved: int
    rejected: int
    pending: int


class FRPTopCountriesResponse(BaseModel):
    entity_type: str
    data: List[CountryCount]


# ── Product Categories ────────────────────────────────────────────────────────
class CategoryCount(BaseModel):
    category: str
    count: int


class FRPProductCategoriesResponse(BaseModel):
    total: int
    data: List[CategoryCount]


# ── Compliance ────────────────────────────────────────────────────────────────
class FRPComplianceResponse(BaseModel):
    pending_requests: int
    avg_days_awaiting: Optional[float]
    issued_this_month: int
    resolved: int


# ── CPR Trend ─────────────────────────────────────────────────────────────────
class FRPCprTrendItem(BaseModel):
    period: str
    received_count: int = 0
    released_count: int = 0


class FRPCprTrendResponse(BaseModel):
    data: List[FRPCprTrendItem]


# ── Recent Activity ───────────────────────────────────────────────────────────
class FRPActivityItem(BaseModel):
    app_no: Optional[str]
    product_name: Optional[str]
    app_status: Optional[str]
    doc_type: Optional[str]
    release_date: Optional[str]
    company: Optional[str]


class FRPRecentActivityResponse(BaseModel):
    data: List[FRPActivityItem]


# ── Alerts ────────────────────────────────────────────────────────────────────
class FRPAlertItem(BaseModel):
    level: str  # critical | warning | info
    message: str


class FRPAlertsResponse(BaseModel):
    data: List[FRPAlertItem]


# ── Applications List (modal) ─────────────────────────────────────────────────
class FRPApplicationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # original fields
    id: Optional[int] = None
    processing_type: Optional[str] = None
    app_type: Optional[str] = None
    app_status: Optional[str] = None
    dtn: Optional[str] = None
    category: Optional[str] = None
    lto_company: Optional[str] = None
    lto_address: Optional[str] = None
    doc_type: Optional[str] = None
    date_released: Optional[str] = None
    date_received: Optional[str] = None
    # ── extra fields returned when advanced filters are active ────────────
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    dosage_form: Optional[str] = None
    manufacturer: Optional[str] = None
    manufacturer_country: Optional[str] = None
    trader: Optional[str] = None
    trader_country: Optional[str] = None
    importer: Optional[str] = None
    importer_country: Optional[str] = None
    distributor: Optional[str] = None
    distributor_country: Optional[str] = None
    repacker: Optional[str] = None
    repacker_country: Optional[str] = None
    uploaded_by: Optional[str] = None
    upload_date: Optional[str] = None
    timeline: Optional[int] = None
    days_elapsed: Optional[int] = None

class FRPApplicationsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[FRPApplicationItem]


# ── Filter Options (advanced filter dropdowns) ────────────────────────────────
class FRPFilterOptionsResponse(BaseModel):
    app_statuses: List[str]
    est_cats: List[str] = []
    doc_types: List[str] = []
    app_types: List[str] = []
    manufacturer_countries: List[str] = []
    trader_countries: List[str] = []
    importer_countries: List[str] = []
    distributor_countries: List[str] = []
    repacker_countries: List[str] = []
