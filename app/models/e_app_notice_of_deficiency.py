# app/models/e_app_notice_of_deficiency.py
import uuid
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

NOD_STATUS_WAITING = "WAITING"
NOD_STATUS_COMPLIED = "COMPLIED"
NOD_STATUS_CLOSED = "CLOSED"


class EAppNoticeOfDeficiency(Base):
    """
    Notice of Deficiency (NOD) for an e-application: what is lacking, the
    documents asked for, and the deadline the applicant has to comply.

    One row per NOD, so an application can have several (the unit allows up
    to five, numbered 1st to 5th by nod_number). Created when the evaluator
    picks the "For Compliance" action.

    "Overdue" is not stored: it is worked out from the dates (still WAITING
    and today is past extended_due_date, or due_date when never extended),
    so it cannot go stale.
    """

    __tablename__ = "e_app_notice_of_deficiency"
    __table_args__ = (
        # an application never has two "2nd NODs"
        UniqueConstraint("application_uuid", "nod_number", name="uq_e_app_notice_of_deficiency_number"),
    )

    nod_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    application_uuid = Column(
        String(36),
        ForeignKey("e_application.application_uuid"),
        nullable=False,
        index=True,
    )

    # The "For Compliance" history row that created this NOD
    history_uuid = Column(
        String(36),
        ForeignKey("e_app_history.history_uuid"),
        nullable=True,
    )

    # Copied from e_application.activity when the NOD is created, so NODs can
    # be filtered by activity (FGMP, MiV-N, CPR) without a join.
    activity = Column(String(255), nullable=False, index=True)

    # 1 to 5
    nod_number = Column(Integer, nullable=False)

    # What is lacking, as written by the evaluator
    deficiencies = Column(Text, nullable=False)

    # Documents asked for, one entry each:
    #   { "requirement_code": "GMP Certificate",
    #     "status": "REQUESTED" | "RECEIVED",
    #     "document_id": <e_app_documents.id once uploaded, else null>,
    #     "filename": <name when received, else null> }
    # The files themselves stay in e_app_documents (Google Drive); this only
    # keeps the list and the links to them.
    requested_documents = Column(JSON, nullable=True)

    # The day the NOD was issued (the worksheet's "Email date")
    issued_date = Column(Date, nullable=False)
    # Days allowed, kept so a future rule change does not alter old NODs
    working_days = Column(Integer, nullable=False, default=5)
    # issued_date + working_days working days
    due_date = Column(Date, nullable=False, index=True)

    # The latest extension, if any
    extended_due_date = Column(Date, nullable=True)
    extension_reason = Column(Text, nullable=True)
    extended_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    extended_at = Column(DateTime, nullable=True)

    # When the applicant complied (empty while still waiting)
    documents_received_date = Column(Date, nullable=True)
    received_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )

    # WAITING | COMPLIED | CLOSED (application ended without compliance)
    status = Column(String(20), nullable=False, default=NOD_STATUS_WAITING)

    issued_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=False
    )

    # Empty until emails are switched on
    email_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(36), ForeignKey("users.user_uuid"), nullable=True)

    application = relationship("EApplication", backref="nods")
    issued_by = relationship("User", foreign_keys=[issued_by_user_uuid])
