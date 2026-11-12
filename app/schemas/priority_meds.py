# app/schemas/priority_meds.py
from typing import List, Optional
from pydantic import BaseModel


class PharmaCategoryBreakdownItem(BaseModel):
    type: str
    generic_name: str
    total_pending: int
    type_total: int

    class Config:
        from_attributes = True


class VaccineBreakdownItem(BaseModel):
    pharma_category: str
    generic_name: str
    total_count: int

    class Config:
        from_attributes = True


class PharmaCategoryBreakdownResponse(BaseModel):
    items: List[PharmaCategoryBreakdownItem]
    grand_total: int


class VaccineBreakdownResponse(BaseModel):
    items: List[VaccineBreakdownItem]
    grand_total: int


class PriorityMedRecord(BaseModel):
    db_id: Optional[str] = None
    dtn: Optional[str] = None
    generic_name: Optional[str] = None
    brand_name: Optional[str] = None


class PriorityMedRecordsResponse(BaseModel):
    data: List[PriorityMedRecord]
    total: int


class PriorityMedGenericName(BaseModel):
    name: str
    count: int


class PriorityMedGenericNamesResponse(BaseModel):
    data: List[PriorityMedGenericName]
