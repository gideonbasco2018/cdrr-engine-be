# app/schemas/recent_applications.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date


class RecentApplicationItem(BaseModel):
    log_id:        int            = Field(..., description="application_logs.id")
    main_db_id:    int            = Field(..., description="application_logs.main_db_id")
    dtn:           str            = Field(..., description="Document Tracking Number (DB_DTN)")
    brand_name:    str            = Field(..., description="DB_PROD_BR_NAME")
    generic_name:  str            = Field(..., description="DB_PROD_GEN_NAME")
    app_step:      str            = Field(..., description="Current application step")
    status_label:  str            = Field(..., description="e.g. 'Completed', 'On Process', 'Backlog'")
    status_color:  str            = Field(..., description="Badge text hex color")
    status_bg:     str            = Field(..., description="Badge background hex color")
    icon:          str            = Field(..., description="Emoji icon")
    date_display:  str            = Field(..., description="Formatted date e.g. 'Mar 10'")
    start_date:    Optional[date] = Field(None, description="Raw start_date from application_logs")

    class Config:
        from_attributes = True


class RecentApplicationsResponse(BaseModel):
    data:     List[RecentApplicationItem]
    count:    int
    username: str

    class Config:
        from_attributes = True