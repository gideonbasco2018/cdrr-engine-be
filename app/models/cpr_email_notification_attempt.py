# app/models/cpr_email_notification_attempt.py
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPREmailNotificationAttempt(Base):
    """
    One row per send/resend attempt. This is what powers the
    "History (N attempts)" list in the UI — each row keeps its own
    outcome and error, so a later successful resend doesn't erase
    the record of an earlier failure.
    """

    __tablename__ = "cpr_email_notification_attempt"

    attempt_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    notification_uuid = Column(
        String(36),
        ForeignKey("cpr_email_notification.notification_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attempt_number = Column(Integer, nullable=False)  # 1, 2, 3, ...
    status = Column(String(20), nullable=False)  # "SENT" | "FAILED"
    error_message = Column(Text, nullable=True)

    attempted_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    attempted_at = Column(DateTime, server_default=func.now())

    notification = relationship(
        "CPREmailNotification", back_populates="attempt_history"
    )
    attempted_by_user = relationship("User", foreign_keys=[attempted_by_user_uuid])
