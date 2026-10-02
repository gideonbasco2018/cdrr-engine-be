# app/models/checklist.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Checklist(Base):
    """
    One batch of DTNs the center forwards. The receiver
    starts a checklist, scans each DTN in the batch into it, then prints /
    exports it as a PDF or Excel checklist.
    """

    __tablename__ = "checklists"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    created_by = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship(
        "ChecklistItem",
        back_populates="checklist",
        cascade="all, delete-orphan",
        order_by="ChecklistItem.id",
    )

    def __repr__(self):
        return f"<Checklist(id={self.id}, created_by={self.created_by!r})>"


class ChecklistItem(Base):
    """One DTN scanned into a checklist. scanned_at is set by the server the
    moment the DTN is scanned/typed in, so it never needs to be filled by hand."""

    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_id = Column(
        Integer, ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dtn = Column(String(50), nullable=False, index=True)
    scanned_by = Column(String(150), nullable=True)
    scanned_at = Column(DateTime(timezone=True), server_default=func.now())

    checklist = relationship("Checklist", back_populates="items")

    # The same DTN can't be scanned twice into one batch (a double trigger
    # of the scanner gun is the usual cause).
    __table_args__ = (UniqueConstraint("checklist_id", "dtn", name="uq_checklist_items_checklist_dtn"),)

    def __repr__(self):
        return f"<ChecklistItem(checklist_id={self.checklist_id}, dtn={self.dtn!r})>"
