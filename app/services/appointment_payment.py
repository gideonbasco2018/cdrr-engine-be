# app/services/appointment_payment.py
import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.e_app_history import EAppHistory
from app.models.e_app_order_of_payment import EAppOrderOfPayment
from app.models.e_app_payment_verification import EAppPaymentVerification
from app.models.e_application import EApplication
from app.services.appointment_claim import CLAIM_STEP, DEL_LAST_INDEX, DEL_THREAD_OPEN

# ADAPT: values written to e_app_history when the payment step is finished
CLOSED_THREAD = "Closed"
COMPLETED_STATUS = "COMPLETED"

CENTS = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENTS)


def post_payments(
    db: Session,
    application: EApplication,
    user_uuid: str,
    payments: list,
    remarks: str | None,
) -> dict:
    """Post cashier payments against the open order of payment.

    Does NOT commit. The caller commits or rolls back.
    Raises PermissionError if the task is not held by the user,
    and ValueError if there is no unpaid order of payment.
    """
    history = (
        db.query(EAppHistory)
        .filter(
            EAppHistory.application_uuid == application.application_uuid,
            EAppHistory.user_uuid == user_uuid,
            EAppHistory.application_step == CLAIM_STEP,
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
        .first()
    )
    if not history:
        raise PermissionError("This task is not currently assigned to you")

    open_op = (
        db.query(EAppOrderOfPayment)
        .filter(
            EAppOrderOfPayment.application_uuid == application.application_uuid,
            EAppOrderOfPayment.status == "UNPAID",
        )
        .order_by(EAppOrderOfPayment.issued_at.desc())
        .with_for_update()
        .first()
    )
    if not open_op:
        raise ValueError("There is no unpaid order of payment for this application")

    batch_uuid = str(uuid.uuid4())
    total_paid = Decimal("0.00")
    for payment in payments:
        amount = _money(payment.amount_paid)
        total_paid += amount
        db.add(
            EAppPaymentVerification(
                op_uuid=open_op.op_uuid,
                posting_batch_uuid=batch_uuid,
                reference_number=open_op.op_number or application.reference_number,
                type_of_payment=payment.type_of_payment,
                official_receipt_number=payment.official_receipt_number.strip(),
                date_of_payment=payment.date_of_payment,
                amount_paid=amount,
                verified_by_user_uuid=user_uuid,
            )
        )

    due = _money(open_op.total_amount)
    balance = max(due - total_paid, Decimal("0.00"))
    overpaid = max(total_paid - due, Decimal("0.00"))

    open_op.paid_at = func.now()
    open_op.payment_reference = ", ".join(
        sorted({p.official_receipt_number.strip() for p in payments})
    )[:255]

    additional_op_number = None
    if balance > 0:
        open_op.status = "PARTIALLY_PAID"

        initial_op = (
            db.query(EAppOrderOfPayment)
            .filter(
                EAppOrderOfPayment.application_uuid == application.application_uuid,
                EAppOrderOfPayment.op_type == "INITIAL",
            )
            .first()
        )
        additional_count = (
            db.query(func.count(EAppOrderOfPayment.op_uuid))
            .filter(
                EAppOrderOfPayment.application_uuid == application.application_uuid,
                EAppOrderOfPayment.op_type == "ADDITIONAL",
            )
            .scalar()
            or 0
        )
        additional_op_number = f"{application.reference_number}-A{additional_count + 1}"

        db.add(
            EAppOrderOfPayment(
                op_uuid=str(uuid.uuid4()),
                application_uuid=application.application_uuid,
                parent_op_uuid=initial_op.op_uuid if initial_op else open_op.op_uuid,
                op_type="ADDITIONAL",
                op_number=additional_op_number,
                application_fee=0,
                lrf_amount=0,
                surcharge=0,
                total_amount=balance,
                deficiency_reason=(remarks or "").strip() or None,
                status="UNPAID",
                issued_by_user_uuid=user_uuid,
            )
        )
        history.application_remarks = (
            f"Insufficient payment (₱{balance:,.2f} short). "
            "For payment verification of additional payment."
        )
    else:
        open_op.status = "PAID"
        history.accomplished_date = func.now()
        history.application_status = COMPLETED_STATUS
        history.del_thread = CLOSED_THREAD
        history.application_remarks = None

    return {
        "reference_number": application.reference_number,
        "fully_paid": balance == 0,
        "total_paid": total_paid,
        "balance": balance,
        "overpaid": overpaid,
        "additional_op_number": additional_op_number,
    }
