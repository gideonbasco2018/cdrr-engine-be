# app/crud/cpr_applications.py
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.e_process import EProcess
from app.models.e_application_ref import EApplicationRef
from app.models.cpr_application import CPRApplication
from app.models.cpr_app_parties import CPRAppParty
from app.models.cpr_app_history import CPRAppHistory
from app.models.cpr_app_document import CPRAppDocument
from app.models.cpr_table_of_changes import CPRTableOfChanges
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

# Confirmed against the seeded e_process row: process_code="MVN",
# process_title="Minor Variation Notification"
CPR_PROCESS_CODE = "MVN"

# Default "next actionable step" per process_code, applied right after
# Initial Submission when the caller doesn't explicitly pass application_step.
# Add an entry here whenever a new process_code is onboarded.
DEFAULT_NEXT_STEP_BY_PROCESS_CODE = {
    "MVN": "Assessor",
}
DEFAULT_NEXT_STEP_FALLBACK = "Assessor"


def _get_default_next_step(process_code: str) -> str:
    return DEFAULT_NEXT_STEP_BY_PROCESS_CODE.get(
        process_code, DEFAULT_NEXT_STEP_FALLBACK
    )


def _get_cpr_process_uuid(db: Session) -> str:
    process = (
        db.query(EProcess)
        .filter(
            EProcess.process_code == CPR_PROCESS_CODE,
            EProcess.is_active.is_(True),
        )
        .first()
    )
    if not process:
        raise HTTPException(
            status_code=500,
            detail=(
                f"e_process row not found/active for "
                f"process_code='{CPR_PROCESS_CODE}'"
            ),
        )
    return process.process_uuid


def create_application(
    db: Session,
    payload: ApplicationCreate,
    documents: list[dict] | None = None,
) -> CPRApplication:
    data = payload.model_dump(by_alias=False)

    # Resolve the process_uuid first, before creating any rows
    process_uuid = _get_cpr_process_uuid(db)
    now = datetime.now(timezone.utc)

    try:
        # 1. Master reference row (e_application_ref) — this is now the "real" PK
        ref_uuid = str(uuid.uuid4())
        db_ref = EApplicationRef(
            ref_uuid=ref_uuid,
            process_uuid=process_uuid,
        )
        db.add(db_ref)
        db.flush()

        # 2. CPR-specific application row (application_uuid == ref_uuid)
        app_data = {k: data[k] for k in APPLICATION_FIELDS}
        db_application = CPRApplication(application_uuid=ref_uuid, **app_data)
        db.add(db_application)
        db.flush()

        # 3. Parties
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

            # 4a. Step 1 — Initial Submission (auto-completed, closed thread)
        db.add(
            CPRAppHistory(
                application_uuid=ref_uuid,
                process_uuid=process_uuid,
                user_uuid=None,  # TODO: set this once a current-user dependency exists
                reference_number=data.get("reference_number"),
                application_step="Initial Submission",
                application_status="Completed",
                start_date=data.get("start_date") or now,
                accomplished_date=now,
                del_index=1,
                del_previous=None,
                del_last_index=0,
                del_thread="Close",
            )
        )

        # 4b. Step 2 — next actionable step, based on process_code (open/active thread)
        default_next_step = _get_default_next_step(CPR_PROCESS_CODE)
        db.add(
            CPRAppHistory(
                application_uuid=ref_uuid,
                process_uuid=process_uuid,
                user_uuid=None,
                reference_number=data.get("reference_number"),
                application_step=data.get("application_step") or default_next_step,
                application_status=data.get("current_status") or "In Progress",
                start_date=now,
                step_duedate=data.get("step_duedate"),
                del_index=2,
                del_previous=1,
                del_last_index=1,
                del_thread="Open",
            )
        )
        # 5. Documents (kung meron)
        if documents:
            for doc_input in documents:
                db.add(CPRAppDocument(application_uuid=ref_uuid, **doc_input))

        # 6. Table of Changes (kung meron)
        for idx, row in enumerate(payload.table_of_changes):
            db.add(
                CPRTableOfChanges(
                    application_uuid=ref_uuid,
                    row_order=idx,
                    current_value=row.current_value,
                    proposed_value=row.proposed_value,
                    specific_type_of_variation=row.specific_type_of_variation,
                )
            )

        db.commit()
        db.refresh(db_application)
        return db_application

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create application")
