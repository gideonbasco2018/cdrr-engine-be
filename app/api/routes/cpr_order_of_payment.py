# api/routes/cpr_order_of_payment.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security_external import verify_bearer_token
from app.schemas.cpr_order_of_payment import (
    OrderOfPaymentCreate,
    OrderOfPaymentResponse,
)
from app.crud import cpr_order_of_payment as crud_op

router = APIRouter(prefix="/api/applications", tags=["Order of Payment"])


@router.post(
    "/{application_uuid}/order-of-payment",
    response_model=OrderOfPaymentResponse,
    dependencies=[Depends(verify_bearer_token)],
)
def create_order_of_payment(
    application_uuid: str,
    payload: OrderOfPaymentCreate,
    db: Session = Depends(get_db),
):
    return crud_op.create_order_of_payment(db, application_uuid, payload)
