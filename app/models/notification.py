# app/models/notification.py

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base_class import Base


class Notification(Base):
    __tablename__ = "notifications"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Who receives this notification
    user_name   = Column(String(255), nullable=False, index=True)

    # Content
    title       = Column(String(255), nullable=False)
    message     = Column(Text, nullable=False)

    # Deep-link reference — DTN of the application
    link_dtn    = Column(String(100), nullable=True)

    # Optional: reference to the specific application_log
    app_log_id  = Column(Integer, ForeignKey("application_logs.id", ondelete="SET NULL"), nullable=True)

    # State
    is_read     = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, "
            f"user={self.user_name}, "
            f"read={self.is_read}, "
            f"title={self.title!r})>"
        )