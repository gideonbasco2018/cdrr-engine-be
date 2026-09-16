# app/models/donation.py

import uuid
from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, ForeignKey, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Donation(Base):
    """
    One row of the CRR "Donation Database" encoding workbook — a donated
    drug product tracked from receipt through evaluation to release.
    Field order mirrors the official upload template (see
    app/api/routes/donation.py TEMPLATE_COLUMNS) so a template download,
    a filled-in upload, and this table always line up column-for-column.

    Most fields are free-text (not typed Date/Numeric) because the
    source workbook itself is loosely formatted — a single cell may hold
    several batch numbers or dates separated by semicolons/newlines.
    """

    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    application_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        server_default=text("(UUID())"),
        index=True,
    )

    # Optimistic concurrency — bumped on every update_donation() call; a
    # write that supplies a stale version is rejected instead of silently
    # overwriting someone else's edit.
    version = Column(Integer, nullable=False, default=1, server_default="1")

    letter_dtn = Column(String(50), nullable=True, index=True)
    date_received = Column(String(50), nullable=True)
    date_received_by_evaluator = Column(String(50), nullable=True)
    donor = Column(String(255), nullable=True)
    donee = Column(String(255), nullable=True)
    registration_dtn = Column(String(50), nullable=True, index=True)
    product_name = Column(Text, nullable=True)
    packaging = Column(Text, nullable=True)
    manufacturer = Column(Text, nullable=True)
    batch_lot_no = Column(String(255), nullable=True)
    expiration_date = Column(String(100), nullable=True)
    total_quantity = Column(String(255), nullable=True)
    validity = Column(String(100), nullable=True)
    date_issued = Column(String(50), nullable=True)
    evaluator = Column(String(50), nullable=True)
    status = Column(
        String(30),
        nullable=False,
        default="For Evaluation",
        server_default="For Evaluation",
        index=True,
    )
    donation_reg_no = Column(String(50), nullable=True)
    date_forwarded_to_checker = Column(String(50), nullable=True)
    date_released = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)

    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    upload_by = Column(String(150), nullable=True)

    created_by = Column(String(150), nullable=True)
    updated_by = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    is_deleted = Column(SmallInteger, nullable=False, default=0, server_default="0", index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(255), nullable=True)

    change_logs = relationship(
        "DonationChangeLog",
        back_populates="donation",
        cascade="all, delete-orphan",
        order_by="DonationChangeLog.changed_at.desc()",
    )

    def __repr__(self):
        return f"<Donation(id={self.id}, letter_dtn={self.letter_dtn!r}, status={self.status!r})>"


class DonationChangeLog(Base):
    """One field-level change captured when a donation record is updated
    via 'Update Information' — powers the row's 'Change Log' action."""

    __tablename__ = "donation_change_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    donation_id = Column(
        Integer, ForeignKey("donations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field = Column(String(100), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String(150), nullable=True)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())

    donation = relationship("Donation", back_populates="change_logs")

    __table_args__ = (Index("ix_donation_change_logs_donation_id", "donation_id"),)

    def __repr__(self):
        return f"<DonationChangeLog(donation_id={self.donation_id}, field={self.field!r})>"
