# FILE: cdrr-engine-be/app/schemas/cdrr_report.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime


# ===== FROO SCHEMAS =====

class FROOReportBase(BaseModel):
    date_received: Optional[date] = None
    date_inspected: Optional[date] = None
    date_endorsed_to_cdrr: Optional[date] = None
    overall_deadline: Optional[date] = None
    approved_extension: Optional[date] = None
    new_overall_deadline: Optional[date] = None
    is_approved: Optional[bool] = None
    date_extension_approved: Optional[date] = None
    status: Optional[str] = None


class FROOReportCreate(FROOReportBase):
    pass


class FROOReportUpdate(BaseModel):
    date_received: Optional[date] = None
    date_inspected: Optional[date] = None
    date_endorsed_to_cdrr: Optional[date] = None
    overall_deadline: Optional[date] = None
    approved_extension: Optional[date] = None
    new_overall_deadline: Optional[date] = None
    is_approved: Optional[bool] = None
    date_extension_approved: Optional[date] = None
    status: Optional[str] = None


class FROOReportResponse(FROOReportBase):
    id: int
    cdrr_report_id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    is_deleted: bool
    
    # Computed field (frontend)
    beyond_within: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ===== CDRR SECONDARY SCHEMAS =====

class CDRRSecondaryBase(BaseModel):
    date_received: Optional[date] = None
    secpa_number: Optional[str] = None
    certificate_number: Optional[str] = None
    date_of_issuance: Optional[date] = None
    type_of_issuance: Optional[str] = None
    product_line: Optional[str] = None
    certificate_validity: Optional[date] = None
    status: Optional[str] = None
    released_date: Optional[date] = None
    overall_deadline: Optional[date] = None


class CDRRSecondaryCreate(CDRRSecondaryBase):
    pass


class CDRRSecondaryUpdate(BaseModel):
    date_received: Optional[date] = None
    secpa_number: Optional[str] = None
    certificate_number: Optional[str] = None
    date_of_issuance: Optional[date] = None
    type_of_issuance: Optional[str] = None
    product_line: Optional[str] = None
    certificate_validity: Optional[date] = None
    status: Optional[str] = None
    released_date: Optional[date] = None
    overall_deadline: Optional[date] = None


class CDRRSecondaryResponse(CDRRSecondaryBase):
    id: int
    cdrr_report_id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    is_deleted: bool
    
    # Computed field (frontend)
    beyond_within: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# ===== MAIN CDRR REPORT SCHEMAS =====

class CDRRReportBase(BaseModel):
    date_received_by_center: Optional[date] = None
    date_decked: Optional[date] = None
    dtn: Optional[str] = None
    name_of_importer: Optional[str] = None
    lto_number: Optional[str] = None
    address: Optional[str] = None
    type_of_application: Optional[str] = None
    evaluator: Optional[str] = None
    date_evaluated: Optional[date] = None
    name_of_foreign_manufacturer: Optional[str] = None
    plant_address: Optional[str] = None
    secpa_number: Optional[str] = None
    certificate_number: Optional[str] = None
    date_of_issuance: Optional[date] = None
    type_of_issuance: Optional[str] = None
    product_line: Optional[str] = None
    certificate_validity: Optional[date] = None
    status: Optional[str] = None
    released_date: Optional[date] = None
    overall_deadline: Optional[date] = None
    category: Optional[str] = None


class CDRRReportCreate(CDRRReportBase):
    """Create CDRR report with optional FROO and Secondary data"""
    froo_report: Optional[FROOReportCreate] = None
    cdrr_secondary: Optional[CDRRSecondaryCreate] = None


class CDRRReportUpdate(BaseModel):
    """Update CDRR report - all fields optional"""
    date_received_by_center: Optional[date] = None
    date_decked: Optional[date] = None
    dtn: Optional[str] = None
    name_of_importer: Optional[str] = None
    lto_number: Optional[str] = None
    address: Optional[str] = None
    type_of_application: Optional[str] = None
    evaluator: Optional[str] = None
    date_evaluated: Optional[date] = None
    name_of_foreign_manufacturer: Optional[str] = None
    plant_address: Optional[str] = None
    secpa_number: Optional[str] = None
    certificate_number: Optional[str] = None
    date_of_issuance: Optional[date] = None
    type_of_issuance: Optional[str] = None
    product_line: Optional[str] = None
    certificate_validity: Optional[date] = None
    status: Optional[str] = None
    released_date: Optional[date] = None
    overall_deadline: Optional[date] = None
    category: Optional[str] = None
    
    # Optional nested updates
    froo_report: Optional[FROOReportUpdate] = None
    cdrr_secondary: Optional[CDRRSecondaryUpdate] = None


class CDRRReportResponse(CDRRReportBase):
    """Response with nested FROO and Secondary data"""
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    is_deleted: bool
    
    # Nested relationships
    froo_report: Optional[FROOReportResponse] = None
    cdrr_secondary: Optional[CDRRSecondaryResponse] = None
    
    # Computed field (frontend)
    beyond_within: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CDRRReportListResponse(BaseModel):
    """Paginated list of CDRR reports"""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: list[CDRRReportResponse]