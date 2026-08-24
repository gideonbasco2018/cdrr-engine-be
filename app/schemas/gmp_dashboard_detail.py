# app/schemas/gmp_dashboard_detail.py
# GMP counterpart of app/schemas/dashboard_detail.py.

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class GMPApplicationLogDetail(BaseModel):
    log_id:             int                = Field(...)
    gmp_id:             Optional[int]      = Field(None)
    dtn:                Optional[str]      = Field(None)
    lto_company:        Optional[str]      = Field(None, description="Establishment name")
    lto_address:        Optional[str]      = Field(None)
    transaction_type:   Optional[str]      = Field(None)
    est_category:       Optional[str]      = Field(None)
    type_of_issuance:   Optional[str]      = Field(None)
    certificate_number: Optional[str]      = Field(None)
    secpa_number:       Optional[str]      = Field(None)
    evaluator:          Optional[str]      = Field(None)
    application_status: Optional[str]      = Field(None)
    del_thread:         Optional[str]      = Field(None)
    app_step:           Optional[str]      = Field(None)
    start_date:         Optional[datetime] = Field(None)
    end_date:           Optional[datetime] = Field(None)
    user_name:          Optional[str]      = Field(None)

    class Config:
        from_attributes = True


class GMPMetricDetailResponse(BaseModel):
    metric:      str                            = Field(..., description="Which KPI was requested")
    username:    str                             = Field(..., description="Effective username")
    date_from:   Optional[date]                  = None
    date_to:     Optional[date]                  = None
    total:       int                             = Field(..., description="Total matching records (before pagination)")
    page:        int                             = Field(1, description="Current page (1-based)")
    page_size:   int                             = Field(10, description="Rows per page")
    total_pages: int                             = Field(..., description="Total number of pages")
    data:        List[GMPApplicationLogDetail]   = Field(default_factory=list)
