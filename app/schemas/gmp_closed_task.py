# app/schemas/gmp_closed_task.py
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GMPCloseTasksRequest(BaseModel):
    # Ids of the ticked Queue rows (GMP_ID). The server closes EVERY reference
    # number under each row's DTN, not just the ticked row.
    record_ids: List[int] = Field(..., min_length=1)
    reason_for_closing: str = Field(..., min_length=1, max_length=255)
    remarks: Optional[str] = None
    date_released: Optional[date] = None
    # Optional, audit only — never written to the record itself.
    type_of_issuance_released: Optional[str] = Field(None, max_length=255)


class GMPClosedDtnResult(BaseModel):
    dtn: Optional[str] = None
    reference_nos: List[str] = []
    open_logs_closed: int = 0


class GMPCloseTasksResponse(BaseModel):
    closed: List[GMPClosedDtnResult]
    total_dtns: int
    total_references: int
    total_logs_closed: int


class GMPClosedTaskResponse(BaseModel):
    id: int
    gmp_record_id: int
    dtn: Optional[int] = None
    reference_no: Optional[str] = None
    closed_by_user_id: int
    closed_by_user_name: str
    reason_for_closing: str
    remarks: Optional[str] = None
    date_released: Optional[date] = None
    type_of_issuance_released: Optional[str] = None
    open_logs_closed: int = 0
    closed_at: datetime
    model_config = ConfigDict(from_attributes=True)
