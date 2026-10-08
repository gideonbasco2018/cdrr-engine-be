# app/api/routes/appointment_records.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.appointment_db import get_appointment_db
from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.appointment_record import AppointmentRecord
from app.models.e_application import EApplication
from app.schemas.appointment_record import (
    AppointmentRecordDetail,
    AppointmentRecordPage,
    ClaimRequest,
    ClaimResult,
)
from app.services.appointment_claim import claim_record, is_claimed

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/appointment-records",
    tags=["Appointment Records"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("", response_model=AppointmentRecordPage)
@router.get("/", response_model=AppointmentRecordPage, include_in_schema=False)
def list_appointment_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
    unclaimed_only: bool = False,
    db: Session = Depends(get_appointment_db),
    internal_db: Session = Depends(get_db),
):
    query = db.query(AppointmentRecord)

    if status:
        query = query.filter(AppointmentRecord.status == status)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                AppointmentRecord.reference_no.ilike(like),
                AppointmentRecord.company_name.ilike(like),
                AppointmentRecord.activity.ilike(like),
            )
        )

    if unclaimed_only:
        claimed = [
            row[0]
            for row in internal_db.query(EApplication.reference_number)
            .filter(EApplication.reference_number.isnot(None))
            .all()
        ]
        if claimed:
            query = query.filter(AppointmentRecord.reference_no.notin_(claimed))

    total = query.count()
    items = (
        query.order_by(AppointmentRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/claim", response_model=list[ClaimResult])
def claim_appointment_records(
    payload: ClaimRequest,
    db: Session = Depends(get_appointment_db),
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    results: list[ClaimResult] = []

    for reference_no in dict.fromkeys(payload.reference_numbers):  # de-duplicate
        if is_claimed(internal_db, reference_no):
            results.append(
                ClaimResult(reference_no=reference_no, result="already_claimed")
            )
            continue

        record = (
            db.query(AppointmentRecord)
            .filter(
                AppointmentRecord.reference_no == reference_no,
                AppointmentRecord.status == "Accepted",
            )
            .first()
        )
        if not record:
            results.append(ClaimResult(reference_no=reference_no, result="not_found"))
            continue

        try:
            claim_record(
                internal_db, record, current_user.user_uuid
            )  # ADAPT: attribute name
            internal_db.commit()
            results.append(ClaimResult(reference_no=reference_no, result="claimed"))
        except IntegrityError:
            # another user claimed it at the same moment (unique reference_number)
            internal_db.rollback()
            results.append(
                ClaimResult(reference_no=reference_no, result="already_claimed")
            )
        except ValueError as err:
            internal_db.rollback()
            results.append(
                ClaimResult(reference_no=reference_no, result="failed", detail=str(err))
            )
        except Exception:
            # Log the real error server-side, but don't leak it to the client and
            # don't abort the batch: earlier references may already be committed.
            internal_db.rollback()
            logger.exception("Unexpected error claiming %s", reference_no)
            results.append(
                ClaimResult(
                    reference_no=reference_no,
                    result="failed",
                    detail="Unexpected error while claiming this record",
                )
            )

    return results


@router.get("/{reference_no}", response_model=AppointmentRecordDetail)
def get_appointment_record(
    reference_no: str,
    db: Session = Depends(get_appointment_db),
):
    record = (
        db.query(AppointmentRecord)
        .filter(AppointmentRecord.reference_no == reference_no)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Appointment record not found")
    return record
