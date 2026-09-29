# app/models/cpr_email_notification.py
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPREmailNotification(Base):
    """
    One row per document (or note) that needs to be emailed to the
    applicant/client. Current status + attempt count live here;
    each individual send/resend attempt is a row in
    CPREmailNotificationAttempt (so failed attempts are never lost
    when a resend succeeds).
    """

    __tablename__ = "cpr_email_notification"

    notification_uuid = Column(
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

    # "ORDER_OF_PAYMENT" | "ADDITIONAL_ORDER_OF_PAYMENT" |
    # "ACKNOWLEDGEMENT_RECEIPT" | "APPLICATION_NOTE"
    document_type = Column(String(50), nullable=False, index=True)

    # Points back to the specific record being emailed, e.g. op_uuid,
    # a posting batch, or the note's uuid. Nullable since not every
    # type needs one (kept generic instead of FK to a single table).
    source_uuid = Column(String(36), nullable=True, index=True)

    # Optional link to the generated PDF, if this email has an attachment
    generated_doc_uuid = Column(
        String(36),
        ForeignKey("cpr_generated_documents.doc_uuid"),
        nullable=True,
    )

    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)  # used for note emails (no attachment)

    # "SENT" | "FAILED" | "SENDING" — reflects the LATEST attempt
    status = Column(String(20), nullable=False, default="SENDING", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    last_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    application = relationship("CPRApplication", backref="email_notifications")
    generated_document = relationship("CPRGeneratedDocument")
    attempt_history = relationship(
        "CPREmailNotificationAttempt",
        back_populates="notification",
        cascade="all, delete-orphan",
        order_by="CPREmailNotificationAttempt.attempt_number",
    )
