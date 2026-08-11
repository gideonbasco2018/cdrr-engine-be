# app/models/lead_assignment.py

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Boolean, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class LeadAssignment(Base):
    """
    One row = one member assigned to a Unit under a specific functional
    role (group_id, from the existing groups table — Checker/Evaluator,
    Evaluator, Preassessor, Admin Support, etc.).

    The old flat lead_user_id / lead_role columns are gone: the "lead"
    for every row is now Unit.lead_user_id, shared by all members of
    that unit — matching one box in the org chart.
    """

    __tablename__ = "lead_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    unit_id = Column(
        Integer, ForeignKey("units.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The one being assigned/monitored
    member_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Functional role of this member WITHIN the unit — sourced from the
    # existing groups table (Checker/Evaluator, Evaluator, Preassessor,
    # Admin Support, Safety & Efficacy, etc.)
    # ⚠️ CONFIRM: adjust the FK target below if your groups table/model
    # is named differently (e.g. app/models/group.py -> "groups").
    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assigned_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    is_active = Column(Boolean, default=True, nullable=False)
    remarks = Column(String(255), nullable=True)

    # Timestamps
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    unassigned_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    unit = relationship("Unit", back_populates="assignments")
    member = relationship("User", foreign_keys=[member_user_id])
    group = relationship("Group", foreign_keys=[group_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])

    def __repr__(self):
        return (
            f"<LeadAssignment(unit_id={self.unit_id}, "
            f"member_id={self.member_user_id}, group_id={self.group_id})>"
        )
