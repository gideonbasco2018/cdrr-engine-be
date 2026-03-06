# ============================================================
# FILE: app/models/bulk_upload_history.py
# ============================================================

from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class BulkUploadHistory(Base):
    __tablename__ = "bulk_upload_history"

    historyID     = Column(Integer,      primary_key=True, index=True, autoincrement=True)
    fileName      = Column(String(255),  nullable=False)
    uploadedAt    = Column(DateTime(timezone=True), server_default=func.now())
    uploadedBy    = Column(String(100),  nullable=False, index=True)  # username string
    insertedCount = Column(Integer,      nullable=False, default=0)
    failedCount   = Column(Integer,      nullable=False, default=0)
    failedRecords = Column(JSON,         nullable=True)               # [{ rsn, remarks, reason }]

    records = relationship(
        "BulkUploadHistoryRecord",
        back_populates="history",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<BulkUploadHistory(id={self.historyID}, file='{self.fileName}', by='{self.uploadedBy}')>"