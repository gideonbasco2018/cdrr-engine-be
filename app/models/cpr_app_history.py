# app/models/cpr_app_history.py
import uuid
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPRAppHistory(Base):
    __tablename__ = "cpr_app_history"

    history_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    application_uuid = Column(
        String(36),
        ForeignKey("cpr_application.application_uuid"),
        nullable=False,
    )

    reference_number = Column(String(255), nullable=True)
    user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True, index=True
    )

    application_step = Column(String(255), nullable=True)
    application_status = Column(String(255), nullable=True, index=True)
    application_decision = Column(String(255), nullable=True)
    application_remarks = Column(Text, nullable=True)

    # Dates
    start_date = Column(DateTime, nullable=True)
    accomplished_date = Column(DateTime, nullable=True)
    step_duedate = Column(String(100), nullable=True)

    # ── Compliance Deadline ─────────────────────────────────────
    deadline_date = Column(Date, nullable=True, index=True)
    working_days = Column(SmallInteger, nullable=True)

    # ── Read tracking ────────────────────────────────────────────
    is_read = Column(SmallInteger, nullable=False, default=0)
    read_at = Column(DateTime, nullable=True)

    # ── Received tracking ──────────────────────────────────────
    is_received = Column(SmallInteger, nullable=False, default=0)
    received_at = Column(DateTime, nullable=True)
    received_by = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    del_index = Column(Integer, nullable=True)
    del_previous = Column(Integer, nullable=True)
    del_last_index = Column(Integer, nullable=True)
    del_thread = Column(String(60), nullable=True, index=True)

    # ── Re-assignment tracking fields ────────────────────────────
    reassigned_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    reassigned_at = Column(DateTime, nullable=True)
    reassigned_from_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    reassigned_to_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    reassignment_reason = Column(String(255), nullable=True)
    reassignment_remarks = Column(Text, nullable=True)

    # ── Re-route tracking fields ─────────────────────────────────
    rerouted_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=True
    )
    rerouted_at = Column(DateTime, nullable=True)
    reroute_from_step = Column(String(255), nullable=True)
    reroute_target_step = Column(String(255), nullable=True)
    reroute_reason = Column(String(255), nullable=True)
    reroute_remarks = Column(Text, nullable=True)
    is_starred = Column(SmallInteger, nullable=False, default=0)
    starred_at = Column(DateTime, nullable=True)

    application = relationship("CPRApplication", back_populates="history")
    # NOTE: multiple FK columns now point to users.user_uuid (user_uuid,
    # reassigned_by/from/to_user_uuid, rerouted_by_user_uuid), so this
    # relationship needs foreign_keys= to avoid AmbiguousForeignKeysError.
    user = relationship("User", foreign_keys=[user_uuid])
