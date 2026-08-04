# app/models/directors_target.py
from sqlalchemy import Column, Integer, Text, Date, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class DirectorsTarget(Base):
    """
    System-wide 'Director's Target' marking on an application_logs task.
    Unlike TargetAssignment (lead -> member scoped), this has no lead
    concept — any director/admin can mark any in-progress task.
    """

    __tablename__ = "directors_target"

    id = Column(Integer, primary_key=True, autoincrement=True)

    application_log_id = Column(
        Integer, ForeignKey("application_logs.id"), nullable=False, index=True
    )
    main_db_id = Column(
        Integer, ForeignKey("main_db.DB_ID"), nullable=False, index=True
    )
    member_user_id = Column(
        Integer, nullable=True, comment="Owner of the task at time of targeting"
    )

    targeted_by_user_id = Column(
        Integer, nullable=False, comment="Director/admin who marked this"
    )

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    remarks = Column(Text, nullable=True)
    target_start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True)

    targeted_at = Column(DateTime, nullable=True, default=func.now())
    untargeted_at = Column(DateTime, nullable=True)

    application_log = relationship("ApplicationLogs", backref="directors_targets")

    __table_args__ = (Index("ix_dt_log_active", "application_log_id", "is_active"),)

    def __repr__(self):
        return f"<DirectorsTarget(id={self.id}, log_id={self.application_log_id}, active={self.is_active})>"
