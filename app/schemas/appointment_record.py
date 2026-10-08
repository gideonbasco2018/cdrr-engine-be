from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AppointmentRecordBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference_no: Optional[str] = None
    appointment_id: Optional[str] = None
    company_name: Optional[str] = None
    activity: Optional[str] = None
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_phone: Optional[str] = None
    submission_type: Optional[str] = None
    status: Optional[str] = None
    assigned_assessor: Optional[str] = None
    application_total_amount: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    assessed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AppointmentRecordListItem(AppointmentRecordBase):
    pass


class AppointmentRecordDetail(AppointmentRecordBase):
    drive_folder_id: Optional[str] = None
    drive_link: Optional[str] = None
    assessment_pdf_link: Optional[str] = None
    assessment_result_drive_link: Optional[str] = None
    assessor_notes: Optional[str] = None
    application_fee: Optional[Decimal] = None
    application_surcharge: Optional[Decimal] = None
    application_lrf: Optional[Decimal] = None
    form_data: Optional[dict[str, Any]] = None
    worksheet_data: Optional[dict[str, Any]] = None
    files_summary: Optional[dict[str, Any]] = None
    dbms_sync: Optional[dict[str, Any]] = None


class AppointmentRecordPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AppointmentRecordListItem]


class ClaimRequest(BaseModel):
    reference_numbers: list[str] = Field(min_length=1, max_length=100)


class ClaimResult(BaseModel):
    reference_no: str
    result: Literal["claimed", "already_claimed", "not_found", "failed"]
    detail: Optional[str] = None


class MyTaskItem(BaseModel):
    application_uuid: str
    reference_number: Optional[str] = None
    activity: Optional[str] = None
    applicant_company: Optional[str] = None
    application_step: Optional[str] = None
    application_status: Optional[str] = None
    application_remarks: Optional[str] = None
    priority: Optional[str] = None
    step_duedate: Optional[str] = None
    deadline_date: Optional[date] = None
    start_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    party_type: str
    name: Optional[str] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    lto_no: Optional[str] = None
    country: Optional[str] = None


class VerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_uuid: str
    reference_number: Optional[str] = None
    type_of_payment: Optional[str] = None
    official_receipt_number: Optional[str] = None
    date_of_payment: Optional[date] = None
    amount_paid: Optional[Decimal] = None
    verified_at: Optional[datetime] = None


class OrderOfPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    op_uuid: str
    op_type: str
    op_number: Optional[str] = None
    parent_op_uuid: Optional[str] = None
    application_fee: Optional[Decimal] = None
    lrf_amount: Optional[Decimal] = None
    surcharge: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    deficiency_reason: Optional[str] = None
    status: str
    issued_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    verifications: list[VerificationOut] = []


class ClaimedApplicationDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_uuid: str
    reference_number: Optional[str] = None
    activity: Optional[str] = None
    applicant_company: Optional[str] = None
    email_address: Optional[str] = None
    contact_no: Optional[str] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    lto_no: Optional[str] = None
    application_type: Optional[str] = None
    drive_folder_id: Optional[str] = None
    drive_link: Optional[str] = None
    form_data: Optional[dict[str, Any]] = None
    parties: list[PartyOut] = []
    orders_of_payment: list[OrderOfPaymentOut] = []


class PaymentIn(BaseModel):
    type_of_payment: str = Field(min_length=1, max_length=50)
    official_receipt_number: str = Field(min_length=1, max_length=100)
    date_of_payment: date
    amount_paid: Decimal = Field(gt=0)


class PostPaymentRequest(BaseModel):
    payments: list[PaymentIn] = Field(min_length=1, max_length=20)
    remarks: Optional[str] = Field(default=None, max_length=500)


class PostPaymentResult(BaseModel):
    reference_number: str
    fully_paid: bool
    total_paid: Decimal
    balance: Decimal
    overpaid: Decimal
    additional_op_number: Optional[str] = None
