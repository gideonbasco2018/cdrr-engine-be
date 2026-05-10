# app/models/lead_assignment.py

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class LeadAssignment(Base):
    """
    Generic lead/member assignment table.
    Supports any role hierarchy: Checker → Evaluator, Supervisor → Evaluator, etc.
    """
    __tablename__ = "lead_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # The one who leads/monitors
    lead_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # The one being led/monitored
    member_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Role context of the lead — e.g. "Checker", "Supervisor"
    lead_role = Column(String(100), nullable=False, index=True)

    # Who created this assignment (Admin)
    assigned_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    is_active = Column(Boolean, default=True, nullable=False)
    remarks = Column(String(255), nullable=True)

    # Timestamps
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    unassigned_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    lead = relationship("User", foreign_keys=[lead_user_id])
    member = relationship("User", foreign_keys=[member_user_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])

    def __repr__(self):
        return (
            f"<LeadAssignment("
            f"lead_id={self.lead_user_id}, "
            f"member_id={self.member_user_id}, "
            f"lead_role={self.lead_role})>"
        )