# app/models/cpr_app_parties.py
import uuid
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class CPRAppParty(Base):
    __tablename__ = "cpr_app_parties"

    party_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    application_uuid = Column(
        String(36),
        ForeignKey("cpr_application.application_uuid"),
        nullable=False,
    )

    party_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=True)
    address = Column(String(500), nullable=True)
    tin = Column(String(50), nullable=True)
    lto_no = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    application = relationship("CPRApplication", back_populates="parties")
