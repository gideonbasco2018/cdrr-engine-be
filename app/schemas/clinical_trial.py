# FILE: app/schemas/clinical_trial.py
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ClinicalTrialBase(BaseModel):
    protocol_no: str = Field(..., max_length=50)

    study_title: Optional[str] = None
    phase: Optional[str] = Field(None, max_length=10)

    sponsor_name: Optional[str] = None
    sponsor_address: Optional[str] = None
    sponsor_contact: Optional[str] = None

    cro_name: Optional[str] = None
    cro_address: Optional[str] = None
    cro_contact: Optional[str] = None

    ct_ref_no: Optional[str] = Field(None, max_length=50)
    ip_name: Optional[str] = None
    dosage_strength: Optional[str] = None
    pharma_form: Optional[str] = None
    drug_type: Optional[str] = None

    il_approval_no: Optional[str] = Field(None, max_length=50)
    il_approval_date: Optional[date] = None
    total_qty_approve: int = 0


class ClinicalTrialCreate(ClinicalTrialBase):
    pass


class ClinicalTrialUpdate(BaseModel):
    protocol_no: Optional[str] = None
    study_title: Optional[str] = None
    phase: Optional[str] = None
    sponsor_name: Optional[str] = None
    sponsor_address: Optional[str] = None
    sponsor_contact: Optional[str] = None
    cro_name: Optional[str] = None
    cro_address: Optional[str] = None
    cro_contact: Optional[str] = None
    ct_ref_no: Optional[str] = None
    ip_name: Optional[str] = None
    dosage_strength: Optional[str] = None
    pharma_form: Optional[str] = None
    drug_type: Optional[str] = None
    il_approval_no: Optional[str] = None
    il_approval_date: Optional[date] = None
    total_qty_approve: Optional[int] = None


class ClinicalTrialOut(ClinicalTrialBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClinicalTrialListResponse(BaseModel):
    total: int
    page: int
    rows_per_page: int
    data: List[ClinicalTrialOut]


class ClinicalTrialUploadResult(BaseModel):
    total_rows: int
    inserted: int
    skipped: int
    errors: List[str] = []
