# app/models/e_process.py
import uuid
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.sql import func

from app.db.base_class import Base


class EProcess(Base):
    __tablename__ = "e_process"

    process_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    process_code = Column(
        String(50), unique=True, nullable=False
    )  # e.g. "VARIATION", "GMP_INITIAL"
    process_title = Column(String(255), nullable=False)  # e.g. "FDA-RRD-LTO Variation"
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
