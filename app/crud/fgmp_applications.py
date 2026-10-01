# app/crud/fgmp_applications.py
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.e_process import EProcess
from app.models.e_application_ref import EApplicationRef
from app.models.e_application import EApplication
from app.models.e_application_fgmp import EApplicationFgmp
from app.models.e_app_parties import EAppParty
from app.models.e_app_history import EAppHistory
from app.models.e_app_documents import EAppDocument
from app.schemas.fgmp_applications import FGMPApplicationCreate

# Shared columns — saved on the mother table (e_application)
APPLICATION_FIELDS = {
    "reference_number",
    "activity",
    "applicant_company",
    "email_address",
    "contact_no",
    "address",
    "tin",
    "lto_no",
    "application_type",
}

# FGMP-only columns — saved on the 1:1 child table (e_application_fgmp)
FGMP_FIELDS = {
    "dtn",
    "related_dtn",
    "date_received",
    "category",
    "foreign_manufacturer",
    "foreign_manufacturer_address",
    "foreign_manufacturer_country",
    "product_line",
    "previous_certificate_number",
    "previous_certificate_validity",
}

# Seeded e_process row: process_code="FGMP",
# process_title="Foreign Good Manufacturing Practice"
FGMP_PROCESS_CODE = "FGMP"

# First actionable step right after Initial Submission
DEFAULT_NEXT_STEP = "Decking"


def _get_fgmp_process_uuid(db: Session) -> str:
    process = (
        db.query(EProcess)
        .filter(
            EProcess.process_code == FGMP_PROCESS_CODE,
            EProcess.is_active.is_(True),
        )
        .first()
    )
    if not process:
        raise HTTPException(
            status_code=500,
            detail=(
                f"e_process row not found/active for "
                f"process_code='{FGMP_PROCESS_CODE}'"
            ),
        )
    return process.process_uuid


def create_application(
    db: Session,
    payload: FGMPApplicationCreate,
    documents: list[dict] | None = None,
) -> EApplication:
    data = payload.model_dump(by_alias=False)

    # Resolve the process_uuid first, before creating any rows
    process_uuid = _get_fgmp_process_uuid(db)
    now = datetime.now(timezone.utc)

    try:
        # 1. Master reference row (e_application_ref)
        ref_uuid = str(uuid.uuid4())
        db.add(EApplicationRef(ref_uuid=ref_uuid, process_uuid=process_uuid))
        db.flush()

        # 2. Mother application row (application_uuid == ref_uuid)
        app_data = {k: data[k] for k in APPLICATION_FIELDS}
        db_application = EApplication(application_uuid=ref_uuid, **app_data)
        db.add(db_application)
        db.flush()

        # 2b. FGMP-only columns (1:1 child row)
        fgmp_data = {k: data[k] for k in FGMP_FIELDS}
        db.add(EApplicationFgmp(application_uuid=ref_uuid, **fgmp_data))

        # 3. Foreign manufacturer — also kept in e_app_parties for consistency
        if data.get("foreign_manufacturer"):
            db.add(
                EAppParty(
                    application_uuid=ref_uuid,
                    party_type="Foreign Manufacturer",
                    name=data["foreign_manufacturer"],
                    address=data.get("foreign_manufacturer_address"),
                    country=data.get("foreign_manufacturer_country"),
                )
            )

        # 4a. Step 1 — Initial Submission (auto-completed, closed thread)
        db.add(
            EAppHistory(
                application_uuid=ref_uuid,
                process_uuid=process_uuid,
                user_uuid=None,
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

        # 4b. Step 2 — next actionable step (open/active thread)
        db.add(
            EAppHistory(
                application_uuid=ref_uuid,
                process_uuid=process_uuid,
                user_uuid=None,
                reference_number=data.get("reference_number"),
                application_step=data.get("application_step") or DEFAULT_NEXT_STEP,
                application_status=data.get("current_status") or "In Progress",
                start_date=now,
                step_duedate=data.get("step_duedate"),
                del_index=2,
                del_previous=1,
                del_last_index=1,
                del_thread="Open",
            )
        )

        # 5. Documents (if any) — shared e_app_documents table
        for doc_input in documents or []:
            db.add(EAppDocument(application_uuid=ref_uuid, **doc_input))

        db.commit()
        db.refresh(db_application)
        return db_application

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create application")
