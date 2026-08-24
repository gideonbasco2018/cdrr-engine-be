# app/schemas/cpr_applications.py
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reference_number: Optional[str] = Field(None, alias="Reference Number")
    activity: Optional[str] = Field(None, alias="Activity")
    applicant_company: Optional[str] = Field(None, alias="Applicant Company")
    email_address: Optional[str] = Field(None, alias="Email Address")
    contact_no: Optional[str] = Field(None, alias="Contact No.")
    address: Optional[str] = Field(None, alias="Address")
    tin: Optional[str] = Field(None, alias="TIN")
    lto_no: Optional[str] = Field(None, alias="LTO No.")
    validity: Optional[str] = Field(None, alias="Validity")
    application_type: Optional[str] = Field(None, alias="Application Type")

    brand_name: Optional[str] = Field(None, alias="Brand Name")
    generic_name: Optional[str] = Field(None, alias="Generic Name")
    dosage_strength: Optional[str] = Field(None, alias="Dosage Strength")
    dosage_form_route: Optional[str] = Field(
        None, alias="Dosage Form and Route of Administration"
    )
    classification: Optional[str] = Field(None, alias="Classification")
    product_category: Optional[str] = Field(None, alias="Product Category")
    essential_drug_list: Optional[str] = Field(None, alias="Essential Drug List")
    pharmacologic_category: Optional[str] = Field(None, alias="Pharmacologic Category")

    shelf_life: Optional[str] = Field(None, alias="Shelf Life")
    storage_condition: Optional[str] = Field(None, alias="Storage Condition")
    packaging: Optional[str] = Field(None, alias="Packaging")
    suggested_retail_price: Optional[str] = Field(None, alias="Suggested Retail Price")
    registration_number: Optional[str] = Field(None, alias="Registration Number")
    mother_application_type: Optional[str] = Field(
        None, alias="Mother Application Type"
    )
    old_rsn_other_dtn: Optional[str] = Field(None, alias="Old RSN/ Other DTN")

    # ── parties (flat, per type) ──
    manufacturer: Optional[str] = Field(None, alias="Manufacturer")
    manufacturer_address: Optional[str] = Field(None, alias="Manufacturer Address")
    manufacturer_tin: Optional[str] = Field(None, alias="Manufacturer TIN")
    manufacturer_lto_no: Optional[str] = Field(None, alias="Manufacturer LTO No.")
    manufacturer_country: Optional[str] = Field(None, alias="Manufacturer Country")

    trader: Optional[str] = Field(None, alias="Trader")
    trader_address: Optional[str] = Field(None, alias="Trader Address")
    trader_tin: Optional[str] = Field(None, alias="Trader TIN")
    trader_lto_no: Optional[str] = Field(None, alias="Trader LTO No.")
    trader_country: Optional[str] = Field(None, alias="Trader Country")

    repacker: Optional[str] = Field(None, alias="Repacker")
    repacker_address: Optional[str] = Field(None, alias="Repacker Address")
    repacker_tin: Optional[str] = Field(None, alias="Repacker TIN")
    repacker_lto_no: Optional[str] = Field(None, alias="Repacker LTO No.")
    repacker_country: Optional[str] = Field(None, alias="Repacker Country")

    importer: Optional[str] = Field(None, alias="Importer")
    importer_address: Optional[str] = Field(None, alias="Importer Address")
    importer_tin: Optional[str] = Field(None, alias="Importer TIN")
    importer_lto_no: Optional[str] = Field(None, alias="Importer LTO No.")
    importer_country: Optional[str] = Field(None, alias="Importer Country")

    distributor: Optional[str] = Field(None, alias="Distributor")
    distributor_address: Optional[str] = Field(None, alias="Distributor Address")
    distributor_tin: Optional[str] = Field(None, alias="Distributor TIN")
    distributor_lto_no: Optional[str] = Field(None, alias="Distributor LTO No.")
    distributor_country: Optional[str] = Field(None, alias="Distributor Country")

    # ── initial history entry ──
    application_step: Optional[str] = None
    current_status: Optional[str] = None
    start_date: Optional[str] = None
    step_duedate: Optional[str] = None


class AppPartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    party_uuid: str
    party_type: str
    name: Optional[str] = None
    address: Optional[str] = None
    tin: Optional[str] = None
    lto_no: Optional[str] = None
    country: Optional[str] = None


class AppHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_uuid: str
    reference_number: Optional[str] = None
    application_step: Optional[str] = None
    application_status: Optional[str] = None
    start_date: Optional[datetime] = None
    step_duedate: Optional[str] = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_uuid: str
    created_at: datetime
    reference_number: Optional[str] = None
    activity: Optional[str] = None
    applicant_company: Optional[str] = None
    application_type: Optional[str] = None
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    registration_number: Optional[str] = None

    parties: List[AppPartyOut] = []
    history: List[AppHistoryOut] = []
