from sqlalchemy import Column, Integer, BigInteger, String, Text, Date, DateTime
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.sql import func
from app.db.base_class import Base
from sqlalchemy.orm import relationship

class MainDB(Base):
    """
    Main database table for pharmaceutical product reports
    Total: 89 columns
    """
    __tablename__ = "main_db"
    
    # Primary Key
    DB_ID = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Establishment Information (10 columns)
    DB_DTN = Column(BigInteger, nullable=True, unique=True, index=True, comment="Document Tracking Number")
    DB_EST_CAT = Column(String(100), nullable=True, index=True, comment="Establishment Category")
    DB_EST_LTO_COMP = Column(Text, nullable=True, comment="LTO Company Name")
    DB_EST_LTO_ADD = Column(Text, nullable=True, comment="LTO Address")
    DB_EST_EADD = Column(Text, nullable=True, comment="Email Address")
    DB_EST_TIN = Column(Text, nullable=True, comment="Tax Identification Number")
    DB_EST_CONTACT_NO = Column(Text, nullable=True, comment="Contact Number")
    DB_EST_LTO_NO = Column(Text, nullable=True, comment="LTO Number")
    DB_EST_VALIDITY = Column(Text, nullable=True, comment="Validity Period")
    
    # Product Information (7 columns)
    DB_PROD_BR_NAME = Column(Text, nullable=True, comment="Brand Name")
    DB_PROD_GEN_NAME = Column(Text, nullable=True, comment="Generic Name")
    DB_PROD_DOS_STR = Column(Text, nullable=True, comment="Dosage Strength")
    DB_PROD_DOS_FORM = Column(Text, nullable=True, comment="Dosage Form")
    DB_PROD_CLASS_PRESCRIP = Column(Text, nullable=True, comment="Prescription Classification")
    DB_PROD_ESS_DRUG_LIST = Column(Text, nullable=True, comment="Essential Drug List")
    DB_PROD_PHARMA_CAT = Column(Text, nullable=True, comment="Pharmaceutical Category")
    
    # Manufacturer Information (5 columns)
    DB_PROD_MANU = Column(Text, nullable=True, comment="Manufacturer Name")
    DB_PROD_MANU_ADD = Column(Text, nullable=True, comment="Manufacturer Address")
    DB_PROD_MANU_TIN = Column(Text, nullable=True, comment="Manufacturer TIN")
    DB_PROD_MANU_LTO_NO = Column(Text, nullable=True, comment="Manufacturer LTO Number")
    DB_PROD_MANU_COUNTRY = Column(Text, nullable=True, comment="Manufacturer Country")
    
    # Trader Information (5 columns)
    DB_PROD_TRADER = Column(Text, nullable=True, comment="Trader Name")
    DB_PROD_TRADER_ADD = Column(Text, nullable=True, comment="Trader Address")
    DB_PROD_TRADER_TIN = Column(Text, nullable=True, comment="Trader TIN")
    DB_PROD_TRADER_LTO_NO = Column(Text, nullable=True, comment="Trader LTO Number")
    DB_PROD_TRADER_COUNTRY = Column(Text, nullable=True, comment="Trader Country")
    
    # Repacker Information (5 columns)
    DB_PROD_REPACKER = Column(Text, nullable=True, comment="Repacker Name")
    DB_PROD_REPACKER_ADD = Column(Text, nullable=True, comment="Repacker Address")
    DB_PROD_REPACKER_TIN = Column(Text, nullable=True, comment="Repacker TIN")
    DB_PROD_REPACKER_LTO_NO = Column(Text, nullable=True, comment="Repacker LTO Number")
    DB_PROD_REPACKER_COUNTRY = Column(Text, nullable=True, comment="Repacker Country")
    
    # Importer Information (5 columns)
    DB_PROD_IMPORTER = Column(Text, nullable=True, comment="Importer Name")
    DB_PROD_IMPORTER_ADD = Column(Text, nullable=True, comment="Importer Address")
    DB_PROD_IMPORTER_TIN = Column(Text, nullable=True, comment="Importer TIN")
    DB_PROD_IMPORTER_LTO_NO = Column(Text, nullable=True, comment="Importer LTO Number")
    DB_PROD_IMPORTER_COUNTRY = Column(Text, nullable=True, comment="Importer Country")
    
    # Distributor Information (6 columns)
    DB_PROD_DISTRI = Column(Text, nullable=True, comment="Distributor Name")
    DB_PROD_DISTRI_ADD = Column(Text, nullable=True, comment="Distributor Address")
    DB_PROD_DISTRI_TIN = Column(Text, nullable=True, comment="Distributor TIN")
    DB_PROD_DISTRI_LTO_NO = Column(Text, nullable=True, comment="Distributor LTO Number")
    DB_PROD_DISTRI_COUNTRY = Column(Text, nullable=True, comment="Distributor Country")
    DB_PROD_DISTRI_SHELF_LIFE = Column(Text, nullable=True, comment="Shelf Life")
    
    # Storage & Packaging (3 columns)
    DB_STORAGE_COND = Column(Text, nullable=True, comment="Storage Conditions")
    DB_PACKAGING = Column(Text, nullable=True, comment="Packaging Details")
    DB_SUGG_RP = Column(Text, nullable=True, comment="Suggested Retail Price")
    
    # Samples & Dates (3 columns)
    DB_NO_SAMPLE = Column(Text, nullable=True, comment="Number of Samples")
    DB_EXPIRY_DATE = Column(Text, nullable=True, comment="Expiry Date")
    DB_CPR_VALIDITY = Column(Text, nullable=True, comment="CPR Validity")
    
    # Registration & Application (7 columns)
    DB_REG_NO = Column(Text, nullable=True, comment="Registration Number")
    DB_APP_TYPE = Column(Text, nullable=True, comment="Application Type")
    DB_MOTHER_APP_TYPE = Column(Text, nullable=True, comment="Mother Application Type")
    DB_OLD_RSN = Column(Text, nullable=True, comment="Old RSN")
    DB_AMMEND1 = Column(Text, nullable=True, comment="Amendment 1")
    DB_AMMEND2 = Column(Text, nullable=True, comment="Amendment 2")
    DB_AMMEND3 = Column(Text, nullable=True, comment="Amendment 3")
    
    # Category & Certification (2 columns)
    DB_PROD_CAT = Column(Text, nullable=True, comment="Product Category")
    DB_CERTIFICATION = Column(Text, nullable=True, comment="Certification")
    
    # Financial Information (6 columns)
    DB_FEE = Column(Text, nullable=True, comment="Fee Amount")
    DB_LRF = Column(Text, nullable=True, comment="LRF Amount")
    DB_SURC = Column(Text, nullable=True, comment="Surcharge Amount")
    DB_TOTAL = Column(Text, nullable=True, comment="Total Amount")
    DB_OR_NO = Column(Text, nullable=True, comment="Official Receipt Number")
    DB_DATE_ISSUED = Column(Text, nullable=True, comment="Date Issued")
    
    # Receiving Dates (3 columns)
    DB_DATE_RECEIVED_FDAC = Column(Text, nullable=True, comment="Date Received FDAC")
    DB_DATE_RECEIVED_CENT = Column(Text, nullable=True, comment="Date Received Central")
    DB_MO = Column(Text, nullable=True, comment="MO")
    
    # Document Information (1 column)
    DB_FILE = Column(Text, nullable=True, comment="File Reference")
    
    # SECPA Information (3 columns)
    DB_SECPA = Column(Text, nullable=True, comment="SECPA")
    DB_SECPA_EXP_DATE = Column(Text, nullable=True, comment="SECPA Expiry Date")
    DB_SECPA_ISSUED_ON = Column(Text, nullable=True, comment="SECPA Issued Date")
    
    # Evaluation & Decking (3 columns)
    DB_DECKING_SCHED = Column(Text, nullable=True, comment="Decking Schedule")
    DB_EVAL = Column(Text, nullable=True, comment="Evaluation")
    DB_DATE_DECK = Column(Text, nullable=True, comment="Date Decked")
    
    # Remarks (2 columns)
    DB_REMARKS_1 = Column(Text, nullable=True, comment="Remarks 1")
    DB_DATE_REMARKS = Column(Text, nullable=True, comment="Date of Remarks")
    
    # Classification & Release (4 columns)
    DB_CLASS = Column(Text, nullable=True, comment="Classification")
    DB_DATE_RELEASED = Column(Text, nullable=True, comment="Date Released")
    DB_TYPE_DOC_RELEASED = Column(Text, nullable=True, comment="Type of Document Released")
    DB_ATTA_RELEASED = Column(Text, nullable=True, comment="Attachment Released")
    
    # CPR Conditions (3 columns)
    DB_CPR_COND = Column(Text, nullable=True, comment="CPR Condition")
    DB_CPR_COND_REMARKS = Column(Text, nullable=True, comment="CPR Condition Remarks")
    DB_CPR_COND_ADD_REMARKS = Column(Text, nullable=True, comment="CPR Condition Additional Remarks")
    
    # Status & Tracking (6 columns)
    DB_APP_STATUS = Column(String(50), nullable=True, index=True, comment="Application Status")
    DB_APP_REMARKS = Column(Text, nullable=True, comment="Application Remarks")
    DB_TRASH = Column(String(50), nullable=True, comment="Trash Status")
    DB_TRASH_DATE_ENCODED = Column(DateTime, nullable=True, comment="Trash Date Encoded")
    DB_USER_UPLOADER = Column(String(255), nullable=True, comment="User Uploader")
    DB_DATE_EXCEL_UPLOAD = Column(DateTime, nullable=True, index=True, 
                                   default=func.now(), comment="Date Excel Uploaded")
    
    # Pharmaceutical Product Category (3 columns)
    DB_PHARMA_PROD_CAT = Column(String(255), nullable=True, comment="Pharmaceutical Product Category")
    DB_PHARMA_PROD_CAT_LABEL = Column(String(255), nullable=True, comment="Pharmaceutical Product Category Label")
    DB_IS_IN_PM = Column(TINYINT, nullable=True, default=0, comment="Is in PM")
    
    def __repr__(self):
        return f"<MainDB(id={self.DB_ID}, dtn={self.DB_DTN}, est_cat={self.DB_EST_CAT})>"
    
    class Config:
        orm_mode = True

    application_delegation = relationship(
        "ApplicationDelegation",
        back_populates="main",
        uselist=False,
        cascade="all, delete-orphan"
    )

    application_logs = relationship(
        "ApplicationLogs",
        back_populates="main_db",
        cascade="all, delete-orphan"
    )
