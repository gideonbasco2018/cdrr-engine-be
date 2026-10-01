# app/models/e_application_mivn.py
import uuid
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class EApplicationMivn(Base):
    """MiV-N-only columns — one row per e_application (1:1)."""

    __tablename__ = "e_application_mivn"

    mivn_uuid = Column(
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

    validity = Column(String(100), nullable=True)

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

    application = relationship("EApplication", back_populates="mivn")
