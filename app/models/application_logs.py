# app/models/application_logs.py

from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    String,
    Text,
    Date,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ApplicationLogs(Base):
    __tablename__ = "application_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Foreign Key - Link to MainDB via DB_ID (BEST PRACTICE)
    main_db_id = Column(
        Integer,
        ForeignKey("main_db.DB_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Application Information
    application_step = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    application_status = Column(String(255), nullable=True, index=True)
    application_decision = Column(String(255), nullable=True)
    application_remarks = Column(Text, nullable=True)

    # Dates
    start_date = Column(DateTime, nullable=True)
    accomplished_date = Column(DateTime, nullable=True)

    # ── Compliance Deadline (NEW) ──────────────────────────────────────
    # Only populated when application_decision = 'For Compliance'
    deadline_date = Column(Date, nullable=True, index=True)  # target deadline
    working_days = Column(SmallInteger, nullable=True)  # e.g. 20

    # ── Read tracking ──────────────────────────────────────────────────
    is_read = Column(SmallInteger, nullable=False, default=0)  # 0 = unread, 1 = read
    read_at = Column(DateTime, nullable=True)  # timestamp when opened

    # User who performed the action
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action_type = Column(String(100), nullable=True, index=True)
    decision_result = Column(String(255), nullable=True, index=True)
    decision_authority_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    decision_authority_name = Column(String(255), nullable=True)
    doctrack_remarks = Column(Text, nullable=True)

    # ── Received tracking ─────────────────────────────────────────────
    is_received = Column(
        SmallInteger, nullable=False, default=0
    )  # 0 = not yet, 1 = received
    received_at = Column(DateTime, nullable=True)  # timestamp when marked received
    received_by = Column(String(255), nullable=True)  # username who marked it

    # Relationship to MainDB (many-to-one)
    main_db = relationship("MainDB", back_populates="application_logs")
    user = relationship("User", foreign_keys=[user_id])

    @property
    def user_first_name(self):
        return self.user.first_name if self.user else None

    @property
    def user_surname(self):
        return self.user.surname if self.user else None

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    del_index = Column(Integer, nullable=True)
    del_previous = Column(Integer, nullable=True)
    del_last_index = Column(Integer, nullable=True)
    del_thread = Column(String(60), nullable=True, index=True)

    # ── Re-assignment tracking fields ─────────────────────────────────
    reassigned_by_user_id = Column(Integer, nullable=True)
    reassigned_by_user_name = Column(String(255), nullable=True)
    reassigned_at = Column(DateTime, nullable=True)
    reassigned_from_user_id = Column(Integer, nullable=True)
    reassigned_from_user_name = Column(String(255), nullable=True)
    reassigned_to_user_id = Column(Integer, nullable=True)
    reassigned_to_user_name = Column(String(255), nullable=True)
    reassignment_reason = Column(String(255), nullable=True)
    reassignment_remarks = Column(Text, nullable=True)

    # ── Re-route tracking fields ───────────────────────────────────────
    rerouted_by_user_id = Column(Integer, nullable=True)
    rerouted_by_user_name = Column(String(255), nullable=True)
    rerouted_at = Column(DateTime, nullable=True)
    reroute_from_step = Column(String(255), nullable=True)
    reroute_target_step = Column(String(255), nullable=True)
    reroute_reason = Column(String(255), nullable=True)
    reroute_remarks = Column(Text, nullable=True)
    is_starred = Column(SmallInteger, nullable=False, default=0)
    starred_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return (
            f"<ApplicationLogs(id={self.id}, "
            f"main_db_id={self.main_db_id}, "
            f"status={self.application_status})>"
        )
