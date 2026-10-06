from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.appointment_db import get_appointment_db
from app.models.appointment_record import AppointmentRecord
from app.schemas.appointment_record import (
    AppointmentRecordDetail,
    AppointmentRecordPage,
)

router = APIRouter(prefix="/api/appointment-records", tags=["Appointment Records"])


@router.get("/", response_model=AppointmentRecordPage)
def list_appointment_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_appointment_db),
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

    total = query.count()
    items = (
        query.order_by(AppointmentRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {"total": total, "page": page, "page_size": page_size, "items": items}


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
