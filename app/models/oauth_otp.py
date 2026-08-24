from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base_class import Base


def default_expiry():
    return datetime.now(timezone.utc) + timedelta(minutes=5)


class OAuthOTP(Base):
    __tablename__ = "oauth_otps"

    id = Column(Integer, primary_key=True, index=True)
    user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=False, index=True
    )

    # hashed OTP — never store plaintext
    otp_hash = Column(String(255), nullable=False)

    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)

    consumed = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), default=default_expiry, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_uuid])
