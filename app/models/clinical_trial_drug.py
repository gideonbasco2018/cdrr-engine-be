# FILE: app/models/clinical_trial_drug.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ClinicalTrialDrug(Base):
    __tablename__ = "clinical_trial_drugs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinical_trial_id = Column(
        Integer,
        ForeignKey("clinical_trials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ip_name = Column(Text, nullable=True)
    dosage_strength = Column(String(100), nullable=True)
    pharma_form = Column(String(100), nullable=True)
    drug_type = Column(Text, nullable=True)
    total_qty_approve = Column(Integer, nullable=False, default=0)

    clinical_trial = relationship("ClinicalTrial", back_populates="drugs")
