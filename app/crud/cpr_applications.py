# app/crud/cpr_applications.py
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.cpr_application import CPRApplication
from app.models.cpr_app_parties import CPRAppParty
from app.models.cpr_app_history import CPRAppHistory
from app.schemas.cpr_applications import ApplicationCreate

PARTY_TYPES = ["manufacturer", "trader", "repacker", "importer", "distributor"]

APPLICATION_FIELDS = {
    "reference_number",
    "activity",
    "applicant_company",
    "email_address",
    "contact_no",
    "address",
    "tin",
    "lto_no",
    "validity",
    "application_type",
    "brand_name",
    "generic_name",
    "dosage_strength",
    "dosage_form_route",
    "classification",
    "product_category",
    "essential_drug_list",
    "pharmacologic_category",
    "shelf_life",
    "storage_condition",
    "packaging",
    "suggested_retail_price",
    "registration_number",
    "mother_application_type",
    "old_rsn_other_dtn",
}


def create_application(db: Session, payload: ApplicationCreate) -> CPRApplication:
    data = payload.model_dump(by_alias=False)

    try:
        # 1. main application row
        app_data = {k: data[k] for k in APPLICATION_FIELDS}
        db_application = CPRApplication(**app_data)
        db.add(db_application)
        db.flush()  # kunin agad yung application_uuid bago gawin yung children

        # 2. parties
        for ptype in PARTY_TYPES:
            name = data.get(ptype)
            if not name:
                continue
            db.add(
                CPRAppParty(
                    application_uuid=db_application.application_uuid,
                    party_type=ptype.capitalize(),
                    name=name,
                    address=data.get(f"{ptype}_address"),
                    tin=data.get(f"{ptype}_tin"),
                    lto_no=data.get(f"{ptype}_lto_no"),
                    country=data.get(f"{ptype}_country"),
                )
            )

        # 3. initial history entry
        db.add(
            CPRAppHistory(
                application_uuid=db_application.application_uuid,
                reference_number=data.get("reference_number"),
                application_step=data.get("application_step"),
                application_status=data.get("current_status"),
                start_date=data.get("start_date"),
                step_duedate=data.get("step_duedate"),
            )
        )

        db.commit()
        db.refresh(db_application)
        return db_application

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create application")
