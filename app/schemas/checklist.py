# app/schemas/checklist.py

import re
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime

# Same 14-digit DTN rule as LETTER_DTN_RE in schemas/donation.py.
DTN_RE = re.compile(r"^\d{14}$")


class ChecklistItemCreate(BaseModel):
    dtn: str

    @field_validator("dtn")
    @classmethod
    def dtn_format(cls, v: str) -> str:
        v = (v or "").strip()
        if not DTN_RE.match(v):
            raise ValueError("DTN must be a 14-digit number.")
        return v


class ChecklistItemResponse(BaseModel):
    id: int
    checklist_id: int
    dtn: str
    scanned_by: Optional[str] = None
    scanned_at: datetime

    class Config:
        from_attributes = True


class ChecklistResponse(BaseModel):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    items: List[ChecklistItemResponse] = []

    class Config:
        from_attributes = True


class ChecklistSummary(BaseModel):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    item_count: int
