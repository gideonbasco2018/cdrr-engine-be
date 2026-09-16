# app/schemas/donation.py

import re
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

# Letter DTN is a 14-digit code (e.g. a YYYYMMDDHHMMSS-style timestamp id)
# — mirrors LETTER_DTN_RE in crud/donation.py (Excel import uses that copy)
# so a manual create/update and an import row are held to the same rule.
LETTER_DTN_RE = re.compile(r"^\d{14}$")


class DonationBase(BaseModel):
    letter_dtn: Optional[str] = None
    date_received: Optional[str] = None
    date_received_by_evaluator: Optional[str] = None
    donor: Optional[str] = None
    donee: Optional[str] = None
    registration_dtn: Optional[str] = None
    product_name: Optional[str] = None
    packaging: Optional[str] = None
    manufacturer: Optional[str] = None
    batch_lot_no: Optional[str] = None
    expiration_date: Optional[str] = None
    total_quantity: Optional[str] = None
    validity: Optional[str] = None
    date_issued: Optional[str] = None
    evaluator: Optional[str] = None
    status: Optional[str] = None
    donation_reg_no: Optional[str] = None
    date_forwarded_to_checker: Optional[str] = None
    date_released: Optional[str] = None
    remarks: Optional[str] = None


class DonationCreate(DonationBase):
    # A row needs a Letter DTN to be inserted — it's how duplicates are
    # detected on import and how the record is identified everywhere else.
    letter_dtn: str
    status: str = "For Evaluation"

    @field_validator("letter_dtn")
    @classmethod
    def letter_dtn_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Letter DTN is required.")
        if not LETTER_DTN_RE.match(v):
            raise ValueError("Letter DTN must be a 14-digit number.")
        return v


class DonationUpdate(DonationBase):
    # The version the client last read — lets the server reject a save
    # that would silently overwrite someone else's edit (optimistic
    # concurrency). Optional so existing callers that don't send it still
    # work; omit it to skip the check.
    version: Optional[int] = None

    @field_validator("letter_dtn")
    @classmethod
    def letter_dtn_not_blank(cls, v: Optional[str]) -> str:
        # The frontend always resends the whole form on save (not a partial
        # patch), so a null/blank here means the user cleared the field —
        # reject it the same way DonationCreate does, so a row can't lose
        # its Letter DTN after the fact.
        if v is None or not v.strip():
            raise ValueError("Letter DTN is required.")
        v = v.strip()
        if not LETTER_DTN_RE.match(v):
            raise ValueError("Letter DTN must be a 14-digit number.")
        return v


class DonationResponse(DonationBase):
    id: int
    application_uuid: str
    status: str
    version: int
    upload_date: Optional[datetime] = None
    upload_by: Optional[str] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DonationChangeLogResponse(BaseModel):
    id: int
    field: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    changed_at: datetime

    class Config:
        from_attributes = True


class DonationUploadResult(BaseModel):
    created: int
    skipped_duplicates: int
    skipped_no_dtn: int = 0
    skipped_invalid_dtn: int = 0
    failed: int
    errors: List[str] = []
