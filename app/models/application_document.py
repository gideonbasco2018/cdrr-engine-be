# app/models/application_document.py

from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # Link to main application record
    main_db_id = Column(
        Integer,
        ForeignKey("main_db.DB_ID", ondelete="CASCADE"),
        nullable=True, 
        index=True,
    )
    # Google Drive info
    drive_file_id   = Column(String(255), nullable=False)           # GDrive file ID
    drive_file_url  = Column(Text, nullable=False)                  # webViewLink
    drive_folder_id = Column(String(255), nullable=True)            # parent folder ID

    # File metadata
    original_filename = Column(String(500), nullable=False)
    mime_type         = Column(String(100), nullable=True)
    file_size_bytes   = Column(Integer, nullable=True)

    # Who uploaded
    uploaded_by_user_id   = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    uploaded_by_user_name = Column(String(255), nullable=True)

    # Soft delete
    is_deleted  = Column(SmallInteger, nullable=False, default=0)
    deleted_at  = Column(DateTime, nullable=True)
    deleted_by  = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Entry classification (para sa folder structure sa Drive)
    db_entry_type = Column(String(255), nullable=False, index=True)
    db_dtn        = Column(String(255), nullable=False, index=True)
    # Optional na sub-classification ng file (hal. "Product Files", "Generated Docs")
    doc_category = Column(String(255), nullable=True, index=True)

    # Relationship
    main_db = relationship("MainDB", back_populates="application_documents")

   

    def __repr__(self):
        return (
            f"<ApplicationDocument(id={self.id}, "
            f"main_db_id={self.main_db_id}, "
            f"filename={self.original_filename})>"
        )