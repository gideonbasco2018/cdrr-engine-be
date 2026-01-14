from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class ApplicationLogs(Base):
    __tablename__ = "application_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Application Information
    application_step = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    application_status = Column(String(255), nullable=True, index=True)
    application_decision = Column(String(255), nullable=True)
    application_remarks = Column(Text, nullable=True)

    # Dates
    start_date = Column(DateTime, nullable=True)
    accomplished_date = Column(DateTime, nullable=True)

    # Foreign Key - Link to MainDB via DTN
    main_db_dtn = Column(Integer, ForeignKey('main_db.DB_DTN', ondelete='CASCADE', onupdate='CASCADE'),
                         nullable=False, index=True)
    
    # Relationship to MainDB
    main_db = relationship("MainDB", backref="application_logs")

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ApplicationLogs(id={self.id}, dtn={self.main_db_dtn}, status={self.application_status})>"
