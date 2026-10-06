from sqlalchemy import Column, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.appointment_db import AppointmentBase


class AppointmentRecord(AppointmentBase):
    """Read-only mapping of the external cdrr_assessment_records table."""

    __tablename__ = "cdrr_assessment_records"

    id = Column(String(64), primary_key=True)
    reference_no = Column(String)
    appointment_id = Column(String)
    company_name = Column(String)
    activity = Column(String(255))
    applicant_name = Column(String)
    applicant_email = Column(String)
    applicant_phone = Column(String)
    submission_type = Column(String)
    drive_folder_id = Column(String)
    drive_link = Column(Text)
    assessment_pdf_link = Column(Text)
    assessment_result_drive_link = Column(Text)
    status = Column(String)
    assessor_notes = Column(Text)
    assigned_assessor = Column(String)

    application_fee = Column(Numeric(12, 2))
    application_surcharge = Column(Numeric(12, 2))
    application_lrf = Column(Numeric(12, 2))
    application_total_amount = Column(Numeric(12, 2))

    form_data = Column(JSONB)
    worksheet_data = Column(JSONB)
    files_summary = Column(JSONB)
    dbms_sync = Column(JSONB)

    submitted_at = Column(DateTime(timezone=True))
    assessed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
