# app/schemas/fgmp_applications.py
from datetime import date, datetime
from typing import Optional, List
from pydantic import AliasChoices, AliasPath, BaseModel, Field, ConfigDict

from app.schemas.mivn_applications import AppPartyOut


def _from_fgmp(name: str):
    """Read a field from the 1:1 e_application_fgmp row (or a flat value)."""
    return Field(None, validation_alias=AliasChoices(name, AliasPath("fgmp", name)))


class FGMPApplicationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # ── e_application (shared) ──
    reference_number: Optional[str] = Field(None, alias="Reference Number")
    activity: Optional[str] = Field(None, alias="Activity")
    applicant_company: Optional[str] = Field(None, alias="Applicant Company")
    email_address: Optional[str] = Field(None, alias="Email Address")
    contact_no: Optional[str] = Field(None, alias="Contact No.")
    address: Optional[str] = Field(None, alias="Address")
    tin: Optional[str] = Field(None, alias="TIN")
    lto_no: Optional[str] = Field(None, alias="LTO No.")
    application_type: Optional[str] = Field(None, alias="Application Type")  # INITIAL | RENEWAL

    # ── e_application_fgmp (FGMP-only) ──
    dtn: Optional[str] = Field(None, alias="DTN")
    related_dtn: Optional[str] = Field(None, alias="Related DTN")
    date_received: Optional[date] = Field(None, alias="Date Received")
    category: Optional[str] = Field(None, alias="Category")
    foreign_manufacturer: Optional[str] = Field(None, alias="Foreign Manufacturer")
    foreign_manufacturer_address: Optional[str] = Field(
        None, alias="Foreign Manufacturer Address"
    )
    foreign_manufacturer_country: Optional[str] = Field(
        None, alias="Foreign Manufacturer Country"
    )
    product_line: Optional[str] = Field(None, alias="Product Line")
    previous_certificate_number: Optional[str] = Field(
        None, alias="Previous Certificate Number"
    )
    previous_certificate_validity: Optional[str] = Field(
        None, alias="Previous Certificate Validity"
    )

    # ── initial history entry ──
    application_step: Optional[str] = None
    current_status: Optional[str] = None
    start_date: Optional[datetime] = None
    step_duedate: Optional[str] = None


class FGMPApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_uuid: str
    created_at: datetime
    reference_number: Optional[str] = None
    activity: Optional[str] = None
    applicant_company: Optional[str] = None
    application_type: Optional[str] = None

    dtn: Optional[str] = _from_fgmp("dtn")
    related_dtn: Optional[str] = _from_fgmp("related_dtn")
    date_received: Optional[date] = _from_fgmp("date_received")
    category: Optional[str] = _from_fgmp("category")
    foreign_manufacturer: Optional[str] = _from_fgmp("foreign_manufacturer")
    foreign_manufacturer_country: Optional[str] = _from_fgmp(
        "foreign_manufacturer_country"
    )
    product_line: Optional[str] = _from_fgmp("product_line")
    previous_certificate_number: Optional[str] = _from_fgmp(
        "previous_certificate_number"
    )
    previous_certificate_validity: Optional[str] = _from_fgmp(
        "previous_certificate_validity"
    )
    type_of_issuance: Optional[str] = _from_fgmp("type_of_issuance")
    certificate_number: Optional[str] = _from_fgmp("certificate_number")

    parties: List[AppPartyOut] = []
