# app/models/e_app_fgmp_worksheet.py
import uuid
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

WORKSHEET_STATUS_DRAFT = "DRAFT"
WORKSHEET_STATUS_SUBMITTED = "SUBMITTED"


class EAppFgmpWorksheet(Base):
    """
    The GMP Clearance Worksheet an FGMP evaluator fills in (Annex 1 for a PIC/S
    member, Annex 2 for a Non-PIC/S member), saved so the Checker and the later
    steps can read it.

    One row per VERSION. While the evaluator works, the latest row is a DRAFT
    that is updated in place. When the application is forwarded, the draft is
    locked (SUBMITTED). If it comes back and the evaluator changes the
    worksheet, a new version is started as a copy, so the earlier version stays
    exactly as the Checker saw it.

    Not stored here, because it is read from where it already lives:
      - the application's own values (manufacturer, LTO, ...)
      - the cashier's OR number/date and the amount
      - the Notices of Deficiency under "deficiency noted"
      - the evaluator's and Checker's names, designations and dates
    """

    __tablename__ = "e_app_fgmp_worksheet"
    __table_args__ = (
        # an application never has two "version 2"s
        UniqueConstraint(
            "application_uuid", "version", name="uq_e_app_fgmp_worksheet_version"
        ),
    )

    worksheet_uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    application_uuid = Column(
        String(36),
        ForeignKey("e_application.application_uuid"),
        nullable=False,
        index=True,
    )

    # The decision that sent this version on (empty while it is a draft)
    history_uuid = Column(
        String(36), ForeignKey("e_app_history.history_uuid"), nullable=True
    )

    # 1, 2, 3 ... one per round
    version = Column(Integer, nullable=False)
    # DRAFT | SUBMITTED (locked)
    status = Column(String(20), nullable=False, default=WORKSHEET_STATUS_DRAFT)
    # "A" = PIC/S member, "B" = Non-PIC/S member, as it was when saved
    variant = Column(String(1), nullable=False)

    # Ticked GMP Evidence items, e.g. ["GMP Certificate", ...]
    gmp_evidence = Column(JSON, nullable=True)
    issuing_authority = Column(String(255), nullable=True)
    issuing_country = Column(String(100), nullable=True)
    foreign_certificate_number = Column(String(100), nullable=True)
    foreign_certificate_validity = Column(String(100), nullable=True)
    # Text, not a date: the unit writes ranges ("13-15 August 2025") and "N/A"
    inspection_dates = Column(String(100), nullable=True)

    # The line the form calls "Date issued", where the evaluator types the GMP
    # evidence statement
    date_issued_text = Column(Text, nullable=True)
    # Worksheet B: "Approved dosage forms: ..."
    approved_dosage_forms_note = Column(Text, nullable=True)

    # Annex B and "Approved Medicinal Products": one entry per row, e.g.
    #   { "dosage_forms": ["Injection", "TPN"], "product_type": "Sterile",
    #     "operations": ["Manufacturing"] }
    applied_forms = Column(JSON, nullable=True)
    approved_products = Column(JSON, nullable=True)

    remarks = Column(Text, nullable=True)
    # Extra notes under "If for compliance, indicate the deficiency noted".
    # The Notices of Deficiency are listed there automatically.
    compliance_notes = Column(Text, nullable=True)

    # The ticked RECOMMENDATION box: APPROVED | FOR INSPECTION |
    # FOR COMPLIANCE | DENIAL, or empty
    recommendation = Column(String(20), nullable=True)

    # Worksheet B, Annex C: the fill-ins ({key: text}) and the rows the
    # evaluator added ([{id, after, contents, remarks}])
    annex_c = Column(JSON, nullable=True)
    annex_rows = Column(JSON, nullable=True)

    saved_by_user_uuid = Column(
        String(36), ForeignKey("users.user_uuid"), nullable=False
    )
    saved_at = Column(DateTime, nullable=False, server_default=func.now())

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String(36), ForeignKey("users.user_uuid"), nullable=True)

    application = relationship("EApplication", backref="fgmp_worksheets")
    saved_by = relationship("User", foreign_keys=[saved_by_user_uuid])
