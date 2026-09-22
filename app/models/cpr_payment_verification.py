# app/models/cpr_payment_verification.py
import uuid
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPRPaymentVerification(Base):
    """
    Cashier-side verification of a payment made against a
    CPROrderOfPayment. This is the "proof of payment" record — the fee
    breakdown itself (application fee, LRF, surcharge) already lives on
    the related CPROrderOfPayment row, so it is not duplicated here.

    verified_by_user_uuid and verified_at are NOT form inputs — set
    them server-side from the logged-in cashier's session at the time
    the record is created, never from client-submitted data.
    """

    __tablename__ = "cpr_payment_verification"

    verification_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # Links this verification to the specific Order of Payment being paid
    op_uuid = Column(
        String(36),
        ForeignKey("cpr_order_of_payment.op_uuid"),
        nullable=False,
        index=True,
    )

    # As typed/looked-up by the cashier — kept as a plain column too
    # (not just derived from op.op_number) in case OP number formatting
    # changes later or a manual reference is used.
    reference_number = Column(String(255), nullable=False, index=True)

    # "CASH" | "CHECK" | "BANK_DEPOSIT" | "ONLINE" (GCash, etc.) — adjust
    # to whatever fixed set of options the cashier's dropdown will use
    type_of_payment = Column(String(50), nullable=False)

    official_receipt_number = Column(String(100), nullable=False, index=True)
    date_of_payment = Column(Date, nullable=False)
    amount_paid = Column(Numeric(12, 2), nullable=False)

    # ── Auto-captured, not cashier input ─────────────────────────
    verified_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=False
    )
    verified_at = Column(DateTime, server_default=func.now())

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # ── Relationships ─────────────────────────────────────────────
    order_of_payment = relationship("CPROrderOfPayment", backref="verifications")
    verified_by_user = relationship("User", foreign_keys=[verified_by_user_uuid])

    def __repr__(self):
        return (
            f"<CPRPaymentVerification(verification_uuid={self.verification_uuid}, "
            f"op_uuid={self.op_uuid}, or_number={self.official_receipt_number}, "
            f"amount_paid={self.amount_paid}, verified_by={self.verified_by_user_uuid})>"
        )
