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
    inserted_by: Optional[str] = None
    inserted_at: datetime
    subject: Optional[str] = None
    subject_status: str = "pending"

    class Config:
        from_attributes = True


class ChecklistBinItemResponse(BaseModel):
    """A soft-removed checklist_items row (is_removed = 1)."""
    id: int
    checklist_id: int
    dtn: str
    inserted_by: Optional[str] = None
    inserted_at: Optional[datetime] = None
    subject: Optional[str] = None
    removed_by: Optional[str] = None
    removed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChecklistUpdate(BaseModel):
    label: Optional[str] = None

    @field_validator("label")
    @classmethod
    def label_clean(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip().upper()
        if len(v) > 50:
            raise ValueError("Label must be 50 characters or less.")
        return v or None


class ChecklistResponse(BaseModel):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    label: Optional[str] = None
    items: List[ChecklistItemResponse] = []

    class Config:
        from_attributes = True


class ChecklistSearchResult(BaseModel):
    """One DTN matching a search, with the checklist it's on."""
    checklist_id: int
    checklist_label: Optional[str] = None
    checklist_created_at: datetime
    item_id: int
    dtn: str
    subject: Optional[str] = None
    subject_status: str


class ChecklistSummary(BaseModel):
    id: int
    created_by: Optional[str] = None
    created_at: datetime
    label: Optional[str] = None
    item_count: int
