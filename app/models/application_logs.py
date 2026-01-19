from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ApplicationLogs(Base):
    __tablename__ = "application_logs"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Foreign Key - Link to MainDB via DB_ID (BEST PRACTICE)
    main_db_id = Column(
        Integer,
        ForeignKey("main_db.DB_ID", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Application Information
    application_step = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    application_status = Column(String(255), nullable=True, index=True)
    application_decision = Column(String(255), nullable=True)
    application_remarks = Column(Text, nullable=True)

    # Dates
    start_date = Column(DateTime, nullable=True)
    accomplished_date = Column(DateTime, nullable=True)

    # Relationship to MainDB (many-to-one)
    main_db = relationship("MainDB", back_populates="application_logs")

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return (
            f"<ApplicationLogs(id={self.id}, "
            f"main_db_id={self.main_db_id}, "
            f"status={self.application_status})>"
        )
