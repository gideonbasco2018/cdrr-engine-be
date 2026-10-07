# app/models/e_application.py
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class EApplication(Base):
    """Mother table of every e-application (MiV-N, FGMP, ...).

    Holds only the columns every application type shares. Type-specific
    columns live in the 1:1 child tables (EApplicationMivn, EApplicationFgmp).
    """

    __tablename__ = "e_application"

    __table_args__ = (
        UniqueConstraint("reference_number", name="uq_e_application_reference_number"),
    )

    application_uuid = Column(
        String(36),
        ForeignKey("e_application_ref.ref_uuid"),
        primary_key=True,
    )

    reference_number = Column(String(255), nullable=True)
    activity = Column(String(255), nullable=True)
    applicant_company = Column(String(255), nullable=True)
    email_address = Column(String(255), nullable=True)
    contact_no = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    tin = Column(String(50), nullable=True)
    lto_no = Column(String(100), nullable=True)
    application_type = Column(
        String(100), nullable=True
    )  # transaction type, e.g. "MiV-N", "INITIAL"

    # Where this application came from (e.g. the external appointment system)
    source_system = Column(String(50), nullable=True)
    source_id = Column(String(64), nullable=True)

    # Google Drive folder of the submitted files
    drive_folder_id = Column(String(255), nullable=True)
    drive_link = Column(Text, nullable=True)

    # Snapshot of the data copied from the source system on claim
    form_data = Column(JSON, nullable=True)
    worksheet_data = Column(JSON, nullable=True)
    files_summary = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parties = relationship(
        "EAppParty", back_populates="application", cascade="all, delete-orphan"
    )
    mivn = relationship("EApplicationMivn", back_populates="application", uselist=False)
    fgmp = relationship("EApplicationFgmp", back_populates="application", uselist=False)
    app_ref = relationship("EApplicationRef")
