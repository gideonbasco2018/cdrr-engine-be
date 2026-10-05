# app/models/e_application.py
from sqlalchemy import Column, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class EApplication(Base):
    """Mother table of every e-application (MiV-N, FGMP, ...).

    Holds only the columns every application type shares. Type-specific
    columns live in the 1:1 child tables (EApplicationMivn, EApplicationFgmp).
    """

    __tablename__ = "e_application"

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
    application_type = Column(String(100), nullable=True)  # transaction type, e.g. "MiV-N", "INITIAL"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parties = relationship(
        "EAppParty", back_populates="application", cascade="all, delete-orphan"
    )
    mivn = relationship(
        "EApplicationMivn", back_populates="application", uselist=False
    )
    fgmp = relationship(
        "EApplicationFgmp", back_populates="application", uselist=False
    )
    app_ref = relationship("EApplicationRef")
