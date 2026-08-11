# app/models/unit.py

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Unit(Base):
    """
    A processing unit/team (e.g. "Facilitated Registration Pathway Unit",
    "Generic Prescription (I, Variation)") headed by one Supervisor/QA
    lead, with an optional QA Admin support person — mirrors one "box" in
    the org chart. Members are assigned to a unit via LeadAssignment,
    each tagged with their functional role (Checker/Evaluator, Evaluator,
    Preassessor, etc.) through group_id.
    """

    __tablename__ = "units"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    # The unit head (e.g. "Chester Joshua V. Saldaña, DVM, FDRO IV")
    lead_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Optional QA Admin support shown under the unit head in the org chart
    qa_admin_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("User", foreign_keys=[lead_user_id])
    qa_admin = relationship("User", foreign_keys=[qa_admin_user_id])
    assignments = relationship(
        "LeadAssignment", back_populates="unit", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Unit(id={self.id}, name={self.name!r})>"
