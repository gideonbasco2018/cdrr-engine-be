from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ApplicationItem(BaseModel):
    # ── application_logs fields ──────────────────────────────────────
    log_id: int
    main_db_id: int
    del_index: Optional[int] = None
    del_thread: Optional[str] = None
    application_step: Optional[str] = None
    application_status: Optional[str] = None
    application_decision: Optional[str] = None
    application_remarks: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # ── main_db fields ───────────────────────────────────────────────
    dtn: Optional[int] = None
    est_cat: Optional[str] = None
    est_lto_comp: Optional[str] = None
    prod_br_name: Optional[str] = None
    prod_gen_name: Optional[str] = None
    app_status: Optional[str] = None

    class Config:
        orm_mode = True


class ApplicationsResponse(BaseModel):
    total: int
    items: List[ApplicationItem]