# FILE: app/models/clinical_trial_audit_log.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base  # adjust import to match your Base declaration


class ClinicalTrialAuditLog(Base):
    __tablename__ = "clinical_trial_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    clinical_trial_id = Column(
        Integer, ForeignKey("clinical_trials.id"), nullable=False, index=True
    )

    action = Column(String(20), nullable=False, default="UPDATE")
    changed_fields = Column(
        Text, nullable=True
    )  # JSON string: {"field": {"old": ..., "new": ...}}
    old_values = Column(Text, nullable=True)  # JSON string snapshot before the update
    new_values = Column(Text, nullable=True)  # JSON string snapshot after the update

    changed_by = Column(Integer, nullable=True)
    changed_at = Column(DateTime, server_default=func.now())

    clinical_trial = relationship("ClinicalTrial", backref="audit_logs")
