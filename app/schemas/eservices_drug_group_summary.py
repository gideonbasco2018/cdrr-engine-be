# app/schemas/drug_group_summary.py
from typing import Optional, List

from pydantic import BaseModel
from enum import Enum


class DrugGroupInfo(BaseModel):
    key: str
    label: str


class DrugGroupSummaryRow(BaseModel):
    pharmacologic_category: Optional[str] = None
    generic_name: Optional[str] = None
    application_count: int
    product_count: int


class ApplicationStatus(str, Enum):
    PENDING = "Pending"
    COMPLETED = "Completed"


class ApplicationStep(str, Enum):
    APPLICATION = "APPLICATION"
    PRE_ASSESSMENT = "PRE-ASSESSMENT"
    EVALUATION = "EVALUATION"
    QUALITY_ASSURANCE = "QUALITY ASSURANCE"
    APPROVAL = "APPROVAL"
    PAYMENT = "PAYMENT"


class DrugGroupSummaryResponse(BaseModel):
    group: str
    application_status: str
    total_application_count: int
    total_product_count: int
    items: List[DrugGroupSummaryRow]
