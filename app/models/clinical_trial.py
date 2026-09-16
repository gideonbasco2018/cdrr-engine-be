# FILE: app/models/clinical_trial.py
import uuid
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, func
from app.db.base_class import Base  # adjust import to match your Base declaration


class ClinicalTrial(Base):
    __tablename__ = "clinical_trials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )

    protocol_no = Column(String(50), nullable=True, index=True)  # no longer unique
    study_title = Column(Text, nullable=True)
    phase = Column(String(10), nullable=True)

    sponsor_name = Column(String(255), nullable=True)
    sponsor_address = Column(String(500), nullable=True)
    sponsor_contact = Column(String(255), nullable=True)

    cro_name = Column(String(255), nullable=True)
    cro_address = Column(String(500), nullable=True)
    cro_contact = Column(String(255), nullable=True)

    ct_ref_no = Column(String(50), nullable=True, index=True)  # no longer unique
    ip_name = Column(Text, nullable=True)
    dosage_strength = Column(String(100), nullable=True)
    pharma_form = Column(String(100), nullable=True)
    drug_type = Column(Text, nullable=True)

    il_approval_no = Column(String(50), nullable=True, index=True)  # no longer unique
    il_approval_date = Column(Date, nullable=True)
    total_qty_approve = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)
