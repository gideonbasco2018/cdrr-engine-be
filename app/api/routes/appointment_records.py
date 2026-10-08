# app/api/routes/appointment_records.py
from typing import Literal
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.appointment_db import get_appointment_db
from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.appointment_record import AppointmentRecord
from app.models.e_app_history import EAppHistory
from app.models.e_application import EApplication
from app.schemas.appointment_record import (
    AppointmentRecordDetail,
    AppointmentRecordPage,
    ClaimedApplicationDetail,
    ClaimRequest,
    ClaimResult,
    MyTaskItem,
    PostPaymentRequest,
    PostPaymentResult,
)
from app.services.appointment_claim import CLAIM_STEP, claim_record, is_claimed
from app.services.appointment_payment import post_payments

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


@router.get("/my-tasks", response_model=list[MyTaskItem])
def list_my_tasks(
    scope: Literal["open", "processed"] = "open",
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    query = (
        internal_db.query(EAppHistory, EApplication)
        .join(
            EApplication,
            EApplication.application_uuid == EAppHistory.application_uuid,
        )
        .filter(
            EAppHistory.user_uuid == current_user.user_uuid,
            EAppHistory.application_step == CLAIM_STEP,
        )
    )
    if scope == "processed":
        query = query.filter(EAppHistory.accomplished_date.isnot(None)).order_by(
            EAppHistory.accomplished_date.desc()
        )
    else:
        query = query.filter(
            EAppHistory.del_thread == "Open",
            EAppHistory.del_last_index == 1,
        ).order_by(EAppHistory.start_date.desc())

    return [
        {
            "application_uuid": app.application_uuid,
            "reference_number": app.reference_number,
            "activity": app.activity,
            "applicant_company": app.applicant_company,
            "application_step": history.application_step,
            "application_status": history.application_status,
            "application_remarks": history.application_remarks,
            "priority": history.priority,
            "step_duedate": history.step_duedate,
            "deadline_date": history.deadline_date,
            "start_date": history.start_date,
            "updated_at": history.updated_at,
        }
        for history, app in query.all()
    ]


@router.get("/claimed/{reference_no}", response_model=ClaimedApplicationDetail)
def get_claimed_application(
    reference_no: str,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # only users who have worked on this application can view it
    has_access = (
        internal_db.query(EAppHistory.history_uuid)
        .filter(
            EAppHistory.application_uuid == application.application_uuid,
            EAppHistory.user_uuid == current_user.user_uuid,
        )
        .first()
        is not None
    )
    if not has_access:
        raise HTTPException(
            status_code=403, detail="You do not have access to this application"
        )

    return application


@router.post("/claimed/{reference_no}/payments", response_model=PostPaymentResult)
def post_claimed_payments(
    reference_no: str,
    payload: PostPaymentRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        result = post_payments(
            internal_db,
            application,
            current_user.user_uuid,
            payload.payments,
            payload.remarks,
        )
        internal_db.commit()
    except PermissionError as err:
        internal_db.rollback()
        raise HTTPException(status_code=403, detail=str(err))
    except ValueError as err:
        internal_db.rollback()
        raise HTTPException(status_code=409, detail=str(err))
    except Exception:
        internal_db.rollback()
        logger.exception("Unexpected error posting payment for %s", reference_no)
        raise HTTPException(
            status_code=500, detail="Unexpected error while posting the payment"
        )

    return result


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
