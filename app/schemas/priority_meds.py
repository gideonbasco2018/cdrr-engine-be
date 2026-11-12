# app/schemas/priority_meds.py
from typing import List
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
