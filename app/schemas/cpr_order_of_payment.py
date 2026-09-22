# app/schemas/cpr_order_of_payment.py
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OrderOfPaymentCreate(BaseModel):
    op_number: Optional[str] = None
    application_fee: Decimal = Field(default=Decimal("0"))
    surcharge: Decimal = Field(default=Decimal("0"))
    lrf_amount: Decimal = Field(default=Decimal("0"))

    # Only relevant when issuing a follow-up OP for a deficient/wrong payment
    op_type: str = Field(default="INITIAL")  # "INITIAL" | "ADDITIONAL"
    parent_op_uuid: Optional[str] = None
    deficiency_reason: Optional[str] = None


class OrderOfPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    op_uuid: str
    application_uuid: str
    op_number: Optional[str] = None
    op_type: str
    status: str
    issued_at: Optional[datetime] = None

    # ── General Information (for the Order of Payment output document) ──
    reference_number: Optional[str] = None
    authorization: str = "Certification"
    type_of_application: Optional[str] = None
    product_type: str = "Drug"
    applicant_company: Optional[str] = None
    email_address: Optional[str] = None
    contact_no: Optional[str] = None

    # ── Payment Details ──
    application_fee: Decimal
    surcharge: Decimal
    lrf_amount: Decimal
    total_amount: Decimal
