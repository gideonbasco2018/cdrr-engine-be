# app/models/cpr_order_of_payment.py
import uuid
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPROrderOfPayment(Base):
    """
    Order of Payment (OP) for a CPR application.

    An application normally has ONE "INITIAL" OP. If the applicant's
    payment turns out to be wrong or insufficient, a follow-up row is
    created with op_type="ADDITIONAL" (a.k.a. Supplemental Order of
    Payment / SOP) and linked back to the original via parent_op_uuid.
    This keeps the full payment history of an application in one table
    instead of duplicating columns across an "initial" and "additional"
    table.
    """

    __tablename__ = "cpr_order_of_payment"

    op_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    application_uuid = Column(
        String(36),
        ForeignKey("cpr_application.application_uuid"),
        nullable=False,
        index=True,
    )

    # Self-reference: only set when op_type == "ADDITIONAL".
    # Points back to the original ("INITIAL") OP row for this application.
    parent_op_uuid = Column(
        String(36),
        ForeignKey("cpr_order_of_payment.op_uuid"),
        nullable=True,
        index=True,
    )

    # "INITIAL" | "ADDITIONAL"
    op_type = Column(String(20), nullable=False, default="INITIAL", index=True)

    # Official OP control number printed on the issued document/slip
    op_number = Column(String(100), nullable=True, index=True)

    # ── Fee breakdown ─────────────────────────────────────────────
    application_fee = Column(Numeric(12, 2), nullable=False, default=0)
    lrf_amount = Column(
        Numeric(12, 2), nullable=False, default=0
    )  # Legal Research Fund
    surcharge = Column(
        Numeric(12, 2), nullable=True, default=0
    )  # penalty for late/deficient payment
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)

    # Only meaningful when op_type == "ADDITIONAL" — why the extra OP was issued
    # e.g. "Underpayment - wrong application type", "Missing LRF"
    deficiency_reason = Column(Text, nullable=True)

    # ── Status tracking ──────────────────────────────────────────
    # "UNPAID" | "PAID" | "CANCELLED"
    status = Column(String(20), nullable=False, default="UNPAID", index=True)

    issued_at = Column(DateTime, server_default=func.now())
    issued_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )

    paid_at = Column(DateTime, nullable=True)
    payment_reference = Column(
        String(255), nullable=True
    )  # O.R. number / cashier reference

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # ── Relationships ──────────────────────────────────────────────
    application = relationship("CPRApplication", backref="orders_of_payment")
    issued_by_user = relationship("User", foreign_keys=[issued_by_user_uuid])

    parent_op = relationship(
        "CPROrderOfPayment",
        remote_side=[op_uuid],
        backref="additional_ops",
    )

    def __repr__(self):
        return (
            f"<CPROrderOfPayment(op_uuid={self.op_uuid}, "
            f"application_uuid={self.application_uuid}, "
            f"op_type={self.op_type}, total_amount={self.total_amount}, "
            f"status={self.status})>"
        )
