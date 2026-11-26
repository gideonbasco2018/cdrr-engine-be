# app/models/gmp_closed_task.py
"""One row per FGMP reference record that was permanently closed with
"Close Task (Final)" from the FGMP Queue — the audit trail (who, when, why)."""
from sqlalchemy import Column, Integer, BigInteger, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.db.base_class import Base


class GMPClosedTask(Base):
    __tablename__ = "gmp_closed_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # ── The application that was closed (one row per reference number) ────────
    gmp_record_id = Column(Integer, ForeignKey("gmp_record.GMP_ID"), nullable=False, index=True)
    dtn = Column(BigInteger, nullable=True, index=True)          # copied for easy lookup
    reference_no = Column(String(50), nullable=True)

    # ── Who closed it ─────────────────────────────────────────────────────────
    closed_by_user_id = Column(Integer, nullable=False)
    closed_by_user_name = Column(String(255), nullable=False)

    # ── The popup's fields ────────────────────────────────────────────────────
    reason_for_closing = Column(String(255), nullable=False)
    remarks = Column(Text, nullable=True)
    date_released = Column(Date, nullable=True)
    # Audit only: the record's own Type of Issuance is never changed by closing.
    type_of_issuance_released = Column(String(255), nullable=True)

    # How many open tasks (in progress / unclaimed / several assignees) this closed.
    open_logs_closed = Column(Integer, nullable=False, default=0, server_default="0")

    closed_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
