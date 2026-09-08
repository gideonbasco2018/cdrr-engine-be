# app/models/gmp_record.py
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime, Date, Index, ForeignKey
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.sql import func
from app.db.base_class import Base
from sqlalchemy.orm import relationship


class GMPRecord(Base):
    """GMP Queue — main record table (29 user-visible columns + metadata)."""
    __tablename__ = "gmp_record"

    GMP_ID = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # ── 29 main columns ──────────────────────────────────────────────────────
    # No longer unique — multiple issuance records (different
    # GMP_TYPE_OF_ISSUANCE, e.g. a Certificate + a later Notice for
    # Inspection) can now share the same DTN. GMP_REFERENCE_NO below is the
    # actual unique identifier per record.
    GMP_DTN = Column(BigInteger, nullable=True, index=True, comment="Document Tracking Number")
    GMP_REFERENCE_NO = Column(String(50), nullable=True, unique=True, index=True,
                               comment="Reference Number — {DTN}-{sequence}, unique per issuance record")
    GMP_RELATED_DTN = Column(Text, nullable=True, comment="Related / Mother DTN")
    GMP_DATE_RECEIVED = Column(Date, nullable=True, comment="Date Received")
    GMP_LTO_COMPANY = Column(Text, nullable=True, comment="Name of Establishment")
    GMP_LTO_NUMBER = Column(Text, nullable=True, comment="LTO Number")
    GMP_LTO_ADDRESS = Column(Text, nullable=True, comment="Address")
    GMP_TRANSACTION_TYPE = Column(Text, nullable=True, comment="Transaction Type")
    GMP_EST_CATEGORY = Column(String(100), nullable=True, index=True, comment="Category")
    GMP_FOREIGN_MANUFACTURER = Column(Text, nullable=True, comment="Foreign Manufacturer")
    GMP_FOREIGN_MANUFACTURER_ADDRESS = Column(Text, nullable=True, comment="Foreign Manufacturer Address")
    GMP_SECPA_NUMBER = Column(Text, nullable=True, comment="SECPA Number")
    GMP_CERTIFICATE_NUMBER = Column(Text, nullable=True, comment="Certificate Number")
    GMP_TYPE_OF_ISSUANCE = Column(Text, nullable=True, comment="Type of Issuance")
    GMP_CERTIFICATE_VALIDITY = Column(Text, nullable=True, comment="Certificate Validity")
    GMP_DECISION = Column(Text, nullable=True, comment="Decision")
    GMP_APP_STATUS = Column(String(50), nullable=True, index=True, comment="Status")
    GMP_RELEASED_DATE = Column(Date, nullable=True, comment="Released Date")
    GMP_PROCESSED_TIME = Column(Text, nullable=True, comment="Processed Time")
    GMP_END_DATE = Column(Date, nullable=True, comment="End Date")
    GMP_TIMELINE = Column(Text, nullable=True, comment="Timeline")
    GMP_REMARKS = Column(Text, nullable=True, comment="Remarks")
    GMP_NOD_DATE_1 = Column(Date, nullable=True, comment="1st Date of NOD")
    GMP_NOD_DATE_2 = Column(Date, nullable=True, comment="2nd Date of NOD")
    GMP_NOD_DATE_3 = Column(Date, nullable=True, comment="3rd Date of NOD")
    GMP_NOD_DATE_4 = Column(Date, nullable=True, comment="4th Date of NOD")
    GMP_NOD_DATE_5 = Column(Date, nullable=True, comment="5th Date of NOD")
    GMP_DATE_PRINTED = Column(Date, nullable=True, comment="Date Printed")
    GMP_COMPLIANCE_DOCS_DATE_RECEIVED = Column(Date, nullable=True, comment="Compliance / Additional Docs Date Received")
    GMP_PRODUCT_LINE = Column(Text, nullable=True, index=True, comment="Product Line / Manufacturing Operation")

    # ── Workflow tracking ────────────────────────────────────────────────────
    GMP_CURRENT_STEP = Column(String(100), nullable=True, index=True, comment="Current Workflow Step")
    GMP_EVALUATOR = Column(Text, nullable=True, comment="Assigned Evaluator")
    GMP_PICS_NONPICS = Column(String(50), nullable=True, index=True, comment="PIC/S or NON PIC/S")

    # ── Soft delete ──────────────────────────────────────────────────────────
    GMP_TRASH = Column(String(50), nullable=True, comment="Trash Status")
    GMP_TRASH_DATE_ENCODED = Column(DateTime, nullable=True, comment="Trash Date Encoded")

    # ── Upload metadata ──────────────────────────────────────────────────────
    GMP_USER_UPLOADER = Column(String(255), nullable=True, comment="User Uploader")
    GMP_DATE_EXCEL_UPLOAD = Column(
        DateTime, nullable=True, index=True, default=func.now(), comment="Date Excel Uploaded"
    )

    __table_args__ = (
        Index("ix_gmp_lto_company", "GMP_LTO_COMPANY", mysql_length=191),
        Index("ix_gmp_transaction_type", "GMP_TRANSACTION_TYPE", mysql_length=50),
        Index("ix_gmp_type_of_issuance", "GMP_TYPE_OF_ISSUANCE", mysql_length=50),
    )

    def __repr__(self):
        return f"<GMPRecord(id={self.GMP_ID}, dtn={self.GMP_DTN})>"

    # Relationships
    gmp_delegation = relationship(
        "GMPDelegation", back_populates="gmp_record", uselist=False, cascade="all, delete-orphan"
    )
    gmp_logs = relationship(
        "GMPApplicationLogs", back_populates="gmp_record", cascade="all, delete-orphan"
    )
    gmp_audit_logs = relationship(
        "GMPFieldAuditLog", back_populates="gmp_record", cascade="all, delete-orphan"
    )


class GMPDelegation(Base):
    """
    1-to-1 delegation tracking — one row per GMP record, updated as steps complete.

    Aligned to the current 6-step live workflow (Decking -> Evaluator -> Checker
    -> QA Admin -> LRD Chief Admin -> OD Receiving -> OD Releasing):
      - GMP_QUALITY_EVALUATOR*  renamed to GMP_EVALUATOR*      ("Quality Evaluator" -> "Evaluator")
      - GMP_DECKER_2*           renamed to GMP_QA_ADMIN*       (2nd-pass decker slot repurposed as QA Admin)
      - GMP_QA_SUPERVISOR*      removed                        (QA Supervisor / FGMP Supervisor group deleted)
      - GMP_DECKER_3*           removed                        (unused 3rd-pass decker slot)
    NOTE: there is still no delegation slot for "LRD Chief Admin" itself in this
    table historically (see GMP_LRD_CHIEF* below, which predates this cleanup and
    was already present) — left as-is since it wasn't part of this change.
    """
    __tablename__ = "gmp_delegation"

    GMP_DELEGATION_ID = Column(Integer, primary_key=True, autoincrement=True)
    GMP_MAIN_ID = Column(
        Integer, ForeignKey("gmp_record.GMP_ID"), nullable=False, unique=True, index=True
    )

    # Step 1 — Decking
    GMP_DECKER_1 = Column(String(255), nullable=True)
    GMP_DECKER_1_DECISION = Column(String(255), nullable=True)
    GMP_DECKER_1_REMARKS = Column(Text, nullable=True)
    GMP_DATE_DECKER_1_END = Column(DateTime, nullable=True)

    # Step 2 — Evaluator (was: Quality Evaluator)
    GMP_EVALUATOR = Column(String(255), nullable=True)
    GMP_EVALUATOR_DECISION = Column(String(255), nullable=True)
    GMP_EVALUATOR_REMARKS = Column(Text, nullable=True)
    GMP_DATE_EVALUATOR_END = Column(DateTime, nullable=True)

    # Step 3 — Checker
    GMP_CHECKER = Column(String(255), nullable=True)
    GMP_CHECKER_DECISION = Column(String(255), nullable=True)
    GMP_CHECKER_REMARKS = Column(Text, nullable=True)
    GMP_DATE_CHECKER_END = Column(DateTime, nullable=True)

    # Step 4 — QA Admin (was: Decker 2nd pass)
    GMP_QA_ADMIN = Column(String(255), nullable=True)
    GMP_QA_ADMIN_DECISION = Column(String(255), nullable=True)
    GMP_QA_ADMIN_REMARKS = Column(Text, nullable=True)
    GMP_DATE_QA_ADMIN_END = Column(DateTime, nullable=True)

    # Step 5 — LRD Chief
    GMP_LRD_CHIEF = Column(String(255), nullable=True)
    GMP_LRD_CHIEF_DECISION = Column(String(255), nullable=True)
    GMP_LRD_CHIEF_REMARKS = Column(Text, nullable=True)
    GMP_DATE_LRD_CHIEF_END = Column(DateTime, nullable=True)

    # Step 6 — OD Receiving
    GMP_OD_RECEIVING = Column(String(255), nullable=True)
    GMP_OD_RECEIVING_DECISION = Column(String(255), nullable=True)
    GMP_OD_RECEIVING_REMARKS = Column(Text, nullable=True)
    GMP_DATE_OD_RECEIVING_END = Column(DateTime, nullable=True)

    # Step 7 — OD Releasing
    GMP_OD_RELEASING = Column(String(255), nullable=True)
    GMP_OD_RELEASING_DECISION = Column(String(255), nullable=True)
    GMP_OD_RELEASING_REMARKS = Column(Text, nullable=True)
    GMP_DATE_OD_RELEASING_END = Column(DateTime, nullable=True)

    gmp_record = relationship("GMPRecord", back_populates="gmp_delegation")


class GMPApplicationLogs(Base):
    """One row per workflow step traversal for a GMP record."""
    __tablename__ = "gmp_application_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gmp_record_id = Column(
        Integer, ForeignKey("gmp_record.GMP_ID"), nullable=False, index=True
    )

    application_step = Column(String(100), nullable=True, index=True)
    user_name = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=True)
    application_status = Column(String(50), nullable=True)   # IN PROGRESS / COMPLETED
    application_decision = Column(Text, nullable=True)
    application_remarks = Column(Text, nullable=True)

    start_date = Column(DateTime, nullable=True)
    accomplished_date = Column(DateTime, nullable=True)

    del_index = Column(Integer, nullable=True)
    del_previous = Column(Integer, nullable=True)
    del_last_index = Column(Integer, nullable=True)
    del_thread = Column(String(20), nullable=True, default="Open")

    is_read = Column(TINYINT, nullable=False, default=0)
    is_starred = Column(TINYINT, nullable=False, default=0)
    starred_at = Column(DateTime, nullable=True)
    received_at = Column(DateTime, nullable=True)
    received_by = Column(String(255), nullable=True)
    is_received = Column(TINYINT, nullable=False, default=0)

    # ── Action / decision tracking (matches production ApplicationLogs) ───────
    action_type = Column(String(100), nullable=True)              # e.g. REASSIGNMENT, REROUTE, or recommendation label
    decision_result = Column(String(255), nullable=True)          # e.g. "For issuance of CPR", "Signed"
    decision_authority_id = Column(Integer, nullable=True)        # user id of signing authority
    decision_authority_name = Column(String(255), nullable=True)  # name of signing authority
    doctrack_remarks = Column(Text, nullable=True)                # remarks sent to doctrack system
    # ── Sent-by tracking (who decked/advanced/forwarded this log to its current assignee) ──
    sent_by_user_id = Column(Integer, nullable=True)
    sent_by_user_name = Column(String(255), nullable=True)    # username (login handle)
    sent_by_full_name = Column(String(255), nullable=True)    # first_name + surname
    sent_by_alias = Column(String(50), nullable=True)         # user's Alias/code, from the users table

    # ── Deadline / compliance tracking ───────────────────────────────────────
    deadline_date = Column(DateTime, nullable=True)
    working_days = Column(Integer, nullable=True)

    # ── Re-assignment tracking ───────────────────────────────────────────────
    reassigned_by_user_id = Column(Integer, nullable=True)
    reassigned_by_user_name = Column(String(255), nullable=True)
    reassigned_at = Column(DateTime, nullable=True)
    reassigned_from_user_id = Column(Integer, nullable=True)
    reassigned_from_user_name = Column(String(255), nullable=True)
    reassigned_to_user_id = Column(Integer, nullable=True)
    reassigned_to_user_name = Column(String(255), nullable=True)
    reassignment_reason = Column(String(255), nullable=True)
    reassignment_remarks = Column(Text, nullable=True)

    # ── Re-route tracking ────────────────────────────────────────────────────
    rerouted_by_user_id = Column(Integer, nullable=True)
    rerouted_by_user_name = Column(String(255), nullable=True)
    rerouted_at = Column(DateTime, nullable=True)
    reroute_from_step = Column(String(100), nullable=True)
    reroute_target_step = Column(String(100), nullable=True)
    reroute_reason = Column(String(255), nullable=True)
    reroute_remarks = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=True, default=func.now())
    updated_at = Column(DateTime, nullable=True, default=func.now(), onupdate=func.now())

    gmp_record = relationship("GMPRecord", back_populates="gmp_logs")

    __table_args__ = (
        Index("ix_gmp_logs_record_step", "gmp_record_id", "application_step"),
    )


class GMPFieldAuditLog(Base):
    """Field-level audit trail — one row per changed field per save action."""
    __tablename__ = "gmp_field_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gmp_record_id = Column(
        Integer, ForeignKey("gmp_record.GMP_ID"), nullable=False, index=True
    )
    field_name = Column(String(100), nullable=False)
    field_label = Column(String(255), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    action_type = Column(String(20), nullable=False, default="UPDATE")
    gmp_log_id = Column(
        Integer, ForeignKey("gmp_application_logs.id"), nullable=True, index=True
    )
    step_context = Column(String(100), nullable=True)
    session_id = Column(String(36), nullable=False, index=True)
    user_name = Column(String(255), nullable=True)
    user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True, default=func.now(), index=True)
    is_critical = Column(TINYINT, nullable=True, default=0)

    gmp_record = relationship("GMPRecord", back_populates="gmp_audit_logs")

    __table_args__ = (
        Index("ix_gmp_audit_record_session", "gmp_record_id", "session_id"),
    )

    def __repr__(self):
        return f"<GMPFieldAuditLog(record={self.gmp_record_id}, field={self.field_name})>"
    