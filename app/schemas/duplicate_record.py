# app/schemas/duplicate_record.py

from typing import Literal, Optional
from pydantic import BaseModel


class DuplicateGroup(BaseModel):
    dupe_key: str
    count: int


class DuplicateRecordRead(BaseModel):
    DB_ID: int
    DB_DTN: Optional[int] = None
    DB_REG_NO: Optional[str] = None
    DB_PROD_BR_NAME: Optional[str] = None
    DB_PROD_GEN_NAME: Optional[str] = None
    DB_EST_LTO_COMP: Optional[str] = None
    DB_APP_STATUS: Optional[str] = None
    DB_DATE_RECEIVED_CENT: Optional[str] = None
    DB_PROCESSING_TYPE: Optional[str] = None

    class Config:
        from_attributes = True


class DuplicateRecordsResponse(BaseModel):
    by: Literal["dtn", "reg_no"]
    duplicate_count: int          # TOTAL duplicate records (lahat, hindi lang current page)
    page: int
    page_size: int
    total_pages: int
    groups: list[DuplicateGroup]  # buong summary, hindi paginated (maliit lang naman ito)
    records: list[DuplicateRecordRead]  # PAGINATED na records