# FILE: cdrr-engine-be/app/models/cdrr_report.py
from sqlalchemy import Column, Integer, String, Date, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class CDRRReport(Base):
    """Main CDRR Report Table (Parent)"""
    __tablename__ = "cdrr_reports"

    id = Column(Integer, primary_key=True, index=True)
    
    # Main CDRR Fields
    date_received_by_center = Column(Date, nullable=True, comment="Date received by center")
    date_decked = Column(Date, nullable=True, comment="Date decked")
    dtn = Column(String(100), nullable=True, index=True, comment="DTN number")
    name_of_importer = Column(String(255), nullable=True, comment="Name of importer")
    lto_number = Column(String(100), nullable=True, comment="LTO number")
    address = Column(Text, nullable=True, comment="Address")
    type_of_application = Column(String(100), nullable=True, comment="Type of application")
    evaluator = Column(String(255), nullable=True, comment="Evaluator name")
    date_evaluated = Column(Date, nullable=True, comment="Date evaluated")
    name_of_foreign_manufacturer = Column(String(255), nullable=True, comment="Foreign manufacturer name")
    plant_address = Column(Text, nullable=True, comment="Plant address")
    secpa_number = Column(String(100), nullable=True, comment="SECPA number")
    certificate_number = Column(String(100), nullable=True, comment="Certificate number")
    date_of_issuance = Column(Date, nullable=True, comment="Date of issuance")
    type_of_issuance = Column(String(100), nullable=True, comment="Type of issuance")
    product_line = Column(String(255), nullable=True, comment="Product line")
    certificate_validity = Column(Date, nullable=True, comment="Certificate validity date")
    status = Column(String(100), nullable=True, comment="Status")
    released_date = Column(Date, nullable=True, comment="Released date")
    overall_deadline = Column(Date, nullable=True, comment="Overall deadline (60 days)")
    category = Column(String(100), nullable=True, comment="Category")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, nullable=True, comment="User ID who created this record")
    updated_by = Column(Integer, nullable=True, comment="User ID who last updated this record")
    is_deleted = Column(Boolean, default=False, comment="Soft delete flag")
    
    # Relationships
    froo_report = relationship("FROOReport", back_populates="cdrr_report", uselist=False, cascade="all, delete-orphan")
    cdrr_secondary = relationship("CDRRSecondary", back_populates="cdrr_report", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CDRRReport(id={self.id}, dtn={self.dtn}, importer={self.name_of_importer})>"


class FROOReport(Base):
    """FROO Report Table (Child of CDRR)"""
    __tablename__ = "froo_reports"

    id = Column(Integer, primary_key=True, index=True)
    cdrr_report_id = Column(Integer, ForeignKey("cdrr_reports.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # FROO Fields
    date_received = Column(Date, nullable=True, comment="Date received by FROO")
    date_inspected = Column(Date, nullable=True, comment="Date inspected")
    date_endorsed_to_cdrr = Column(Date, nullable=True, comment="Date endorsed to CDRR (COC/RL)")
    overall_deadline = Column(Date, nullable=True, comment="FROO overall deadline")
    approved_extension = Column(Date, nullable=True, comment="Approved extension (3 months)")
    new_overall_deadline = Column(Date, nullable=True, comment="New overall deadline after extension")
    is_approved = Column(Boolean, default=False, comment="Approved flag")
    date_extension_approved= Column(Date, nullable=True, comment="Date extension was approved")
    status = Column(String(100), nullable=True, comment="Status")
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, nullable=True, comment="User ID who created this record")
    updated_by = Column(Integer, nullable=True, comment="User ID who last updated this record")
    is_deleted = Column(Boolean, default=False, comment="Soft delete flag")
    
    # Relationship
    cdrr_report = relationship("CDRRReport", back_populates="froo_report")

    def __repr__(self):
        return f"<FROOReport(id={self.id}, cdrr_report_id={self.cdrr_report_id})>"


class CDRRSecondary(Base):
    """CDRR Secondary/Additional Fields Table (Child of CDRR)"""
    __tablename__ = "cdrr_secondary"

    id = Column(Integer, primary_key=True, index=True)
    cdrr_report_id = Column(Integer, ForeignKey("cdrr_reports.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Additional CDRR Fields
    date_received = Column(Date, nullable=True, comment="Date received (CDRR)")
    secpa_number = Column(String(100), nullable=True, comment="SECPA number")
    certificate_number = Column(String(100), nullable=True, comment="Certificate number")
    date_of_issuance = Column(Date, nullable=True, comment="Date of issuance")
    type_of_issuance = Column(String(100), nullable=True, comment="Type of issuance")
    product_line = Column(String(255), nullable=True, comment="Product line")
    certificate_validity = Column(Date, nullable=True, comment="Certificate validity")
    status = Column(String(100), nullable=True, comment="Status")
    released_date = Column(Date, nullable=True, comment="Released date")
    overall_deadline = Column(Date, nullable=True, comment="Overall deadline 60 days")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, nullable=True, comment="User ID who created this record")
    updated_by = Column(Integer, nullable=True, comment="User ID who last updated this record")
    is_deleted = Column(Boolean, default=False, comment="Soft delete flag")
    
    # Relationship
    cdrr_report = relationship("CDRRReport", back_populates="cdrr_secondary")

    def __repr__(self):
        return f"<CDRRSecondary(id={self.id}, cdrr_report_id={self.cdrr_report_id})>"