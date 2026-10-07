# app/services/appointment_claim.py
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment_record import AppointmentRecord
from app.models.e_app_history import EAppHistory
from app.models.e_app_order_of_payment import EAppOrderOfPayment
from app.models.e_app_parties import EAppParty
from app.models.e_application import EApplication
from app.models.e_application_ref import EApplicationRef
from app.models.e_process import EProcess

# ADAPT: values must match e_process.process_code in your database
PROCESS_CODE_BY_ACTIVITY = {
    "CDRR Certificate of Product Registration": "CPR",
}

CLAIM_STEP = "Payment Verification/Posting"
CLAIM_STATUS = "IN PROGRESS"

# Task ownership convention for e_app_history
DEL_INDEX = 3
DEL_PREVIOUS = 2
DEL_LAST_INDEX = 1  # marks who currently holds the task
DEL_THREAD_OPEN = "Open"

PARTY_TYPES = ["Manufacturer", "Trader", "Repacker", "Importer", "Distributor"]


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def is_claimed(db: Session, reference_no: str) -> bool:
    return (
        db.query(EApplication.application_uuid)
        .filter(EApplication.reference_number == reference_no)
        .first()
        is not None
    )


def claim_record(db: Session, record: AppointmentRecord, user_uuid: str) -> str:
    """Copy one external record into the internal e_* tables.

    Does NOT commit. The caller commits or rolls back so that every
    claim is one transaction. Returns the new application_uuid.
    """
    form = record.form_data or {}

    process_code = PROCESS_CODE_BY_ACTIVITY.get(record.activity)
    process = (
        db.query(EProcess)
        .filter(EProcess.process_code == process_code, EProcess.is_active.is_(True))
        .first()
        if process_code
        else None
    )
    if not process:
        raise ValueError(f"No process configured for activity: {record.activity}")

    ref = EApplicationRef(process_uuid=process.process_uuid)
    db.add(ref)
    db.flush()  # ref_uuid is needed as the PK of e_application

    db.add(
        EApplication(
            application_uuid=ref.ref_uuid,
            reference_number=record.reference_no,
            activity=record.activity,
            applicant_company=record.company_name,
            email_address=record.applicant_email,
            contact_no=record.applicant_phone,
            address=_text(form.get("Address")),
            tin=_text(form.get("TIN")),
            lto_no=_text(form.get("LTO No.")),
            application_type=_text(form.get("Application Type")),
            source_system="appointment",
            source_id=record.id,
            drive_folder_id=record.drive_folder_id,
            drive_link=record.drive_link,
            form_data=record.form_data,
            worksheet_data=record.worksheet_data,
            files_summary=record.files_summary,
        )
    )
    db.flush()  # a duplicate reference_number fails here (unique constraint)

    # form_data -> e_app_parties (one row per party that has a name)
    for party_type in PARTY_TYPES:
        name = _text(form.get(party_type))
        if not name:
            continue
        db.add(
            EAppParty(
                application_uuid=ref.ref_uuid,
                party_type=party_type,
                name=name,
                address=_text(form.get(f"{party_type} Address")),
                tin=_text(form.get(f"{party_type} TIN")),
                lto_no=_text(form.get(f"{party_type} LTO No.")),
                country=_text(form.get(f"{party_type} Country")),
            )
        )

    # fee columns -> e_app_order_of_payment
    db.add(
        EAppOrderOfPayment(
            application_uuid=ref.ref_uuid,
            op_type="INITIAL",
            application_fee=record.application_fee or 0,
            lrf_amount=record.application_lrf or 0,
            surcharge=record.application_surcharge or 0,
            total_amount=record.application_total_amount or 0,
            status="UNPAID",
        )
    )

    # task ownership -> e_app_history
    db.add(
        EAppHistory(
            application_uuid=ref.ref_uuid,
            process_uuid=process.process_uuid,
            reference_number=record.reference_no,
            user_uuid=user_uuid,
            application_step=CLAIM_STEP,
            application_status=CLAIM_STATUS,
            start_date=func.now(),
            del_index=DEL_INDEX,
            del_previous=DEL_PREVIOUS,
            del_last_index=DEL_LAST_INDEX,
            del_thread=DEL_THREAD_OPEN,
        )
    )

    return ref.ref_uuid
