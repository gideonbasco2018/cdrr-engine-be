# app/models/cpr_application.py
import uuid
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPRApplication(Base):
    __tablename__ = "cpr_application"

    application_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    reference_number = Column(String(255), nullable=True)
    activity = Column(String(255), nullable=True)
    applicant_company = Column(String(255), nullable=True)
    email_address = Column(String(255), nullable=True)
    contact_no = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    tin = Column(String(50), nullable=True)
    lto_no = Column(String(100), nullable=True)
    validity = Column(String(100), nullable=True)
    application_type = Column(String(100), nullable=True)

    brand_name = Column(String(255), nullable=True)
    generic_name = Column(String(255), nullable=True)
    dosage_strength = Column(String(255), nullable=True)
    dosage_form_route = Column(String(255), nullable=True)
    classification = Column(String(255), nullable=True)
    product_category = Column(String(255), nullable=True)
    essential_drug_list = Column(String(255), nullable=True)
    pharmacologic_category = Column(String(255), nullable=True)

    shelf_life = Column(String(255), nullable=True)
    storage_condition = Column(String(255), nullable=True)
    packaging = Column(String(255), nullable=True)
    suggested_retail_price = Column(String(100), nullable=True)
    registration_number = Column(String(100), nullable=True)
    mother_application_type = Column(String(100), nullable=True)
    old_rsn_other_dtn = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parties = relationship(
        "CPRAppParty", back_populates="application", cascade="all, delete-orphan"
    )
    history = relationship(
        "CPRAppHistory", back_populates="application", cascade="all, delete-orphan"
    )
