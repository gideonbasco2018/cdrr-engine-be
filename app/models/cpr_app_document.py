# app/models/cpr_app_document.py
from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class CPRAppDocument(Base):
    __tablename__ = "cpr_app_documents"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    application_uuid = Column(
        String(36),
        ForeignKey("cpr_application.application_uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    application_type = Column(String(100), nullable=False, index=True)  # e.g. "MiV-N"

    # "technical" | "general"
    requirement_group = Column(String(20), nullable=False, index=True)

    # e.g. "MiV-N1" — null for general requirements (no variation)
    category_code = Column(String(50), nullable=True, index=True)

    # Corresponds to req.id in the frontend
    requirement_code = Column(String(100), nullable=False, index=True)

    # Google Drive information
    drive_file_id = Column(String(255), nullable=False)
    drive_file_url = Column(Text, nullable=False)
    drive_folder_id = Column(String(255), nullable=True)

    # File metadata
    original_filename = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Uploader information
    uploaded_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    uploaded_by_user_name = Column(String(255), nullable=True)

    # Soft delete
    is_deleted = Column(SmallInteger, nullable=False, default=0)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    application = relationship("CPRApplication", backref="documents")

    def __repr__(self):
        return (
            f"<CPRAppDocument(id={self.id}, "
            f"application_uuid={self.application_uuid}, "
            f"requirement_group={self.requirement_group}, "
            f"category_code={self.category_code}, "
            f"requirement_code={self.requirement_code}, "
            f"filename={self.original_filename})>"
        )
