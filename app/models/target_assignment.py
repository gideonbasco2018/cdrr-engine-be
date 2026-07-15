# app/models/target_assignment.py

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    DateTime,
    Date,
    Boolean,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class TargetAssignment(Base):
    """
    Marks a specific application_logs task (currently sitting with a member)
    as a "target" that the lead wants to prioritize / monitor closely.

    One row per application_log_id — mark/unmark just toggles is_active,
    it doesn't create a new row each time (mirrors how the dummy UI
    treats target status as a simple Set toggle).
    """

    __tablename__ = "target_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # The specific task instance being targeted
    application_log_id = Column(
        Integer,
        ForeignKey("application_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Denormalized — lets you query/join straight to main_db without
    # going through application_logs every time
    main_db_id = Column(
        Integer,
        ForeignKey("main_db.DB_ID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The member currently holding the task (should mirror
    # application_logs.user_id at the time it was targeted)
    member_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The lead who marked it as target
    lead_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Optional — which lead_assignments row justified this action (audit trail)
    lead_assignment_id = Column(
        Integer,
        ForeignKey("lead_assignments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_active = Column(Boolean, default=True, nullable=False, index=True)
    remarks = Column(String(255), nullable=True)

    # ── Target period ──────────────────────────────────────────────
    # When the lead intends monitoring to start/end for this task.
    # Set (or updated) at the same time is_active is turned on.
    target_start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True, index=True)

    # Timestamps
    targeted_at = Column(DateTime(timezone=True), server_default=func.now())
    untargeted_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    application_log = relationship("ApplicationLogs")
    main_db = relationship("MainDB")
    member = relationship("User", foreign_keys=[member_user_id])
    lead = relationship("User", foreign_keys=[lead_user_id])
    lead_assignment = relationship("LeadAssignment", foreign_keys=[lead_assignment_id])

    __table_args__ = (
        # One target record per task — mark/unmark toggles is_active
        # instead of inserting a new row each time.
        UniqueConstraint("application_log_id", name="uq_target_application_log"),
    )

    def __repr__(self):
        return (
            f"<TargetAssignment(id={self.id}, "
            f"application_log_id={self.application_log_id}, "
            f"lead_user_id={self.lead_user_id}, "
            f"is_active={self.is_active})>"
        )
