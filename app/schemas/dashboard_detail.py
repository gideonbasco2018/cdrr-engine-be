# app/schemas/dashboard_detail.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class ApplicationLogDetail(BaseModel):
    log_id:               int            = Field(...)
    dtn:                  Optional[str]  = Field(None)
    lto_company:          Optional[str]  = Field(None, description="LTO Company Name")
    lto_address:          Optional[str]  = Field(None)   # ← dagdag
    brand_name:           Optional[str]  = Field(None)
    generic_name:         Optional[str]  = Field(None)
    secpa:                Optional[str]  = Field(None)   # ← dagdag
    app_type:             Optional[str]  = Field(None)   # ← dagdag
    reg_no:               Optional[str]  = Field(None)   # ← dagdag
    atta_released:        Optional[str]  = Field(None)   # ← dagdag
    application_status:   Optional[str]  = Field(None)
    del_thread:           Optional[str]  = Field(None)
    app_step:             Optional[str]  = Field(None)
    start_date:           Optional[datetime] = Field(None)
    end_date:             Optional[datetime] = Field(None)
    user_name:            Optional[str]  = Field(None)

    class Config:
        from_attributes = True


class MetricDetailResponse(BaseModel):
    metric:       str                        = Field(..., description="Which KPI was requested")
    username:     str                        = Field(..., description="Effective username")
    date_from:    Optional[date]             = None
    date_to:      Optional[date]             = None
    total:        int                        = Field(..., description="Total matching records (before pagination)")
    page:         int                        = Field(1, description="Current page (1-based)")
    page_size:    int                        = Field(10, description="Rows per page")
    total_pages:  int                        = Field(..., description="Total number of pages")
    data:         List[ApplicationLogDetail] = Field(default_factory=list)