# app/models/e_app_table_of_changes.py
import uuid
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class EAppTableOfChanges(Base):
    """
    "Table of Changes" under Post-Approval Changes Particulars.
    One row = one Current -> Proposed change entry for an e-application.
    """

    __tablename__ = "e_app_table_of_changes"

    change_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    application_uuid = Column(
        String(36),
        ForeignKey("e_application.application_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Keeps row order stable when re-rendering the form/PDF
    row_order = Column(Integer, nullable=False, default=0)

    current_value = Column(Text, nullable=True)
    proposed_value = Column(Text, nullable=True)

    # e.g. "MiV-PHN1" or "MiV-PH-N7 (MaV-15)" when it references the
    # original variation code applied for the PCPR
    specific_type_of_variation = Column(String(255), nullable=True)

    application = relationship("EApplication", backref="table_of_changes")

    def __repr__(self):
        return (
            f"<EAppTableOfChanges(change_uuid={self.change_uuid}, "
            f"application_uuid={self.application_uuid}, "
            f"variation={self.specific_type_of_variation})>"
        )
