# app/crud/cpr_order_of_payment.py
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.cpr_application import CPRApplication
from app.models.cpr_order_of_payment import CPROrderOfPayment
from app.schemas.cpr_order_of_payment import (
    OrderOfPaymentCreate,
    OrderOfPaymentResponse,
)


def create_order_of_payment(
    db: Session,
    application_uuid: str,
    payload: OrderOfPaymentCreate,
) -> OrderOfPaymentResponse:
    application = (
        db.query(CPRApplication)
        .filter(CPRApplication.application_uuid == application_uuid)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if payload.op_type == "ADDITIONAL" and not payload.parent_op_uuid:
        raise HTTPException(
            status_code=422,
            detail="parent_op_uuid is required when op_type is 'ADDITIONAL'",
        )

    # "Type of Application" comes from the process this application was
    # filed under (e_process.process_title), reached via e_application_ref
    type_of_application = None
    if application.app_ref and application.app_ref.process:
        type_of_application = application.app_ref.process.process_title

    total_amount = payload.application_fee + payload.surcharge + payload.lrf_amount

    try:
        db_op = CPROrderOfPayment(
            application_uuid=application_uuid,
            parent_op_uuid=payload.parent_op_uuid,
            op_type=payload.op_type,
            op_number=payload.op_number,
            application_fee=payload.application_fee,
            surcharge=payload.surcharge,
            lrf_amount=payload.lrf_amount,
            total_amount=total_amount,
            deficiency_reason=payload.deficiency_reason,
            status="UNPAID",
        )
        db.add(db_op)
        db.commit()
        db.refresh(db_op)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create Order of Payment")

    return OrderOfPaymentResponse(
        op_uuid=db_op.op_uuid,
        application_uuid=db_op.application_uuid,
        op_number=db_op.op_number,
        op_type=db_op.op_type,
        status=db_op.status,
        issued_at=db_op.issued_at,
        reference_number=application.reference_number,
        type_of_application=type_of_application,
        applicant_company=application.applicant_company,
        email_address=application.email_address,
        contact_no=application.contact_no,
        application_fee=db_op.application_fee,
        surcharge=db_op.surcharge,
        lrf_amount=db_op.lrf_amount,
        total_amount=db_op.total_amount,
    )
