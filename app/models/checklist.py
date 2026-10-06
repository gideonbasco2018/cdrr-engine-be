# app/models/checklist.py

from sqlalchemy import (
    Column, Computed, Integer, SmallInteger, String, Text, DateTime, ForeignKey, UniqueConstraint, and_,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Checklist(Base):
    """
    One batch of DTNs the center forwards. The receiver
    starts a checklist, inserts each DTN in the batch into it, then prints /
    exports it as a PDF or Excel checklist.

    Deleting a checklist is a soft delete only — the row and its DTNs stay,
    flagged with is_deleted/deleted_at/deleted_by, and are hidden from the page.
    """

    __tablename__ = "checklists"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    created_by = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Free-text tag for the batch (e.g. "URGENT", "CPR") — printed big on the PDF.
    label = Column(String(50), nullable=True)

    is_deleted = Column(SmallInteger, nullable=False, default=0, server_default="0", index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(150), nullable=True)

    # Only the DTNs still on the checklist — removed ones (the Bin) are left out.
    items = relationship(
        "ChecklistItem",
        primaryjoin=lambda: and_(
            Checklist.id == ChecklistItem.checklist_id, ChecklistItem.is_removed == 0
        ),
        order_by="ChecklistItem.id",
        viewonly=True,
    )

    def __repr__(self):
        return f"<Checklist(id={self.id}, created_by={self.created_by!r})>"


class ChecklistItem(Base):
    """One DTN inserted into a checklist. inserted_at is set by the server the
    moment the DTN goes in, so it never needs to be filled by hand.

    Removing a DTN is a soft remove: is_removed = 1 plus removed_by/removed_at
    (those two stay NULL for DTNs that were never removed). Removed rows make
    up the checklist's Bin and can't be restored — to put a DTN back it has
    to be inserted again, which makes a new row with a new insert time."""

    __tablename__ = "checklist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checklist_id = Column(
        Integer, ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dtn = Column(String(50), nullable=False, index=True)
    inserted_by = Column(String(150), nullable=True)
    inserted_at = Column(DateTime(timezone=True), server_default=func.now())

    # The DTN's subject, copied from FIS (document_tracker.docreceivingtbl)
    # right after the insert and kept as it was then. subject_status:
    #   pending   — lookup not done yet (it runs in the background)
    #   found     — subject copied from FIS
    #   not_found — FIS has no document with this DTN
    #   error     — FIS couldn't be reached; "Refresh subjects" retries
    subject = Column(Text, nullable=True)
    subject_status = Column(String(20), nullable=False, default="pending", server_default="pending")

    is_removed = Column(SmallInteger, nullable=False, default=0, server_default="0", index=True)
    removed_by = Column(String(150), nullable=True)
    removed_at = Column(DateTime(timezone=True), nullable=True)

    # The DTN while it's on the checklist, NULL once removed — filled in by
    # MySQL itself. The unique key below is on this, so the same DTN can't be
    # on one checklist twice, yet a removed DTN can be inserted again (MySQL
    # allows any number of NULLs in a unique key).
    active_dtn = Column(
        String(50),
        Computed("(case when `is_removed` = 0 then `dtn` else NULL end)", persisted=True),
    )

    checklist = relationship("Checklist")

    __table_args__ = (
        UniqueConstraint("checklist_id", "active_dtn", name="uq_checklist_items_checklist_active_dtn"),
    )

    def __repr__(self):
        return f"<ChecklistItem(checklist_id={self.checklist_id}, dtn={self.dtn!r})>"
