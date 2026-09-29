# app/models/cpr_app_note.py
import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPRAppNote(Base):
    __tablename__ = "cpr_app_notes"

    note_uuid = Column(
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

    author_user_uuid = Column(String(36), ForeignKey("users.user_uuid"), nullable=False)
    note_text = Column(Text, nullable=False)

    # Whether the author requested this note be emailed to participants.
    # Actual send status/history lives in CPREmailNotification —
    # this flag just says "an email was requested for this note".
    email_requested = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, server_default=func.now())

    application = relationship("CPRApplication", backref="notes")
    author = relationship("User", foreign_keys=[author_user_uuid])
