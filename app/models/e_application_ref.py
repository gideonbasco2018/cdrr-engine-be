# app/models/e_application_ref.py
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class EApplicationRef(Base):
    __tablename__ = "e_application_ref"

    ref_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    process_uuid = Column(
        String(36), ForeignKey("e_process.process_uuid"), nullable=False
    )
    created_at = Column(DateTime, server_default=func.now())

    # ── Soft-delete tracking ──────────────────────────────
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(36), ForeignKey("users.user_uuid"), nullable=True)

    process = relationship("EProcess")
    history = relationship(
        "CPRAppHistory", back_populates="app_ref", cascade="all, delete-orphan"
    )
