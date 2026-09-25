# FILE: app/schemas/clinical_trial.py
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class ClinicalTrialDrugBase(BaseModel):
    ip_name: Optional[str] = None
    dosage_strength: Optional[str] = None
    pharma_form: Optional[str] = None
    drug_type: Optional[str] = None
    total_qty_approve: int = 0


class ClinicalTrialDrugCreate(ClinicalTrialDrugBase):
    pass


class ClinicalTrialDrugOut(ClinicalTrialDrugBase):
    id: int

    class Config:
        from_attributes = True


class ClinicalTrialBase(BaseModel):
    protocol_no: Optional[str] = Field(None, max_length=50)
    study_title: Optional[str] = None
    # Widened to match the "Others" free-text option in the Update form,
    # not just the fixed I/II/III/IV/combo presets.
    phase: Optional[str] = Field(None, max_length=20)

    sponsor_name: Optional[str] = None
    sponsor_address: Optional[str] = None
    sponsor_contact: Optional[str] = None

    cro_name: Optional[str] = None
    cro_address: Optional[str] = None
    cro_contact: Optional[str] = None

    ct_ref_no: Optional[str] = Field(None, max_length=50)

    il_approval_no: Optional[str] = Field(None, max_length=50)
    il_approval_date: Optional[date] = None


class ClinicalTrialCreate(ClinicalTrialBase):
    drugs: List[ClinicalTrialDrugCreate] = []


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
    il_approval_no: Optional[str] = None
    il_approval_date: Optional[date] = None
    drugs: Optional[List[ClinicalTrialDrugCreate]] = None


class ClinicalTrialOut(ClinicalTrialBase):
    id: int
    uuid: str
    drugs: List[ClinicalTrialDrugOut] = []
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


class ClinicalTrialUploadPreviewRow(BaseModel):
    row_number: int  # first row of the group
    protocol_no: Optional[str] = None
    study_title: Optional[str] = None
    phase: Optional[str] = None
    sponsor_name: Optional[str] = None
    ct_ref_no: Optional[str] = None
    drug_count: int = 0


class ClinicalTrialUploadPreviewResult(BaseModel):
    total_rows: int
    valid_count: int
    error_count: int
    valid_rows: List[ClinicalTrialUploadPreviewRow]
    errors: List[str] = []
