# app/models/e_application_fgmp.py
import uuid
from sqlalchemy import Column, Date, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class EApplicationFgmp(Base):
    """FGMP-only columns — one row per e_application (1:1)."""

    __tablename__ = "e_application_fgmp"

    fgmp_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    application_uuid = Column(
        String(36),
        ForeignKey("e_application.application_uuid"),
        nullable=False,
    )

    dtn = Column(String(50), nullable=True, index=True)
    related_dtn = Column(String(50), nullable=True)  # Renewal only
    date_received = Column(Date, nullable=True)
    category = Column(String(100), nullable=True)  # PIC/S | NON PIC/S

    # Also saved as an e_app_parties row (party_type="Foreign Manufacturer")
    foreign_manufacturer = Column(String(255), nullable=True)
    foreign_manufacturer_address = Column(String(500), nullable=True)
    foreign_manufacturer_country = Column(String(100), nullable=True)
    product_line = Column(String(500), nullable=True)

    # Renewal only — the clearance being renewed
    previous_certificate_number = Column(String(100), nullable=True)
    previous_certificate_validity = Column(String(100), nullable=True)

    # Filled in during evaluation — not part of the create payload
    type_of_issuance = Column(String(255), nullable=True)
    certificate_number = Column(String(100), nullable=True)

    application = relationship("EApplication", back_populates="fgmp")
