# FILE: cdrr-engine-be/app/crud/cdrr_report.py
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc
from typing import Optional
from datetime import datetime

from app.models.cdrr_report import CDRRReport, FROOReport, CDRRSecondary
from app.schemas.cdrr_report import (
    CDRRReportCreate,
    CDRRReportUpdate,
    FROOReportUpdate,
    CDRRSecondaryUpdate
)


def create_cdrr_report(
    db: Session,
    report: CDRRReportCreate,
    user_id: int
) -> CDRRReport:
    """Create a new CDRR report with optional FROO and Secondary data"""
    # Create main CDRR report
    cdrr_data = report.model_dump(exclude={'froo_report', 'cdrr_secondary'})
    db_report = CDRRReport(
        **cdrr_data,
        created_by=user_id,
        updated_by=user_id
    )
    db.add(db_report)
    db.flush()  # Get the ID without committing
    
    # Create FROO report if provided
    if report.froo_report:
        froo_data = report.froo_report.model_dump()
        db_froo = FROOReport(
            **froo_data,
            cdrr_report_id=db_report.id,
            created_by=user_id,
            updated_by=user_id
        )
        db.add(db_froo)
    
    # Create CDRR Secondary if provided
    if report.cdrr_secondary:
        secondary_data = report.cdrr_secondary.model_dump()
        db_secondary = CDRRSecondary(
            **secondary_data,
            cdrr_report_id=db_report.id,
            created_by=user_id,
            updated_by=user_id
        )
        db.add(db_secondary)
    
    db.commit()
    db.refresh(db_report)
    return db_report


def get_cdrr_report(db: Session, report_id: int) -> Optional[CDRRReport]:
    """Get a single CDRR report with nested data"""
    return db.query(CDRRReport).options(
        joinedload(CDRRReport.froo_report),
        joinedload(CDRRReport.cdrr_secondary)
    ).filter(
        and_(
            CDRRReport.id == report_id,
            CDRRReport.is_deleted == False
        )
    ).first()


def get_cdrr_reports(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc"
) -> tuple[list[CDRRReport], int]:
    """
    Get paginated list of CDRR reports with filtering
    Returns (reports, total_count)
    """
    query = db.query(CDRRReport).options(
        joinedload(CDRRReport.froo_report),
        joinedload(CDRRReport.cdrr_secondary)
    ).filter(CDRRReport.is_deleted == False)
    
    # Search filter
    if search:
        search_filter = or_(
            CDRRReport.dtn.ilike(f"%{search}%"),
            CDRRReport.name_of_importer.ilike(f"%{search}%"),
            CDRRReport.lto_number.ilike(f"%{search}%"),
            CDRRReport.name_of_foreign_manufacturer.ilike(f"%{search}%"),
            CDRRReport.certificate_number.ilike(f"%{search}%"),
        )
        query = query.filter(search_filter)
    
    # Status filter
    if status:
        query = query.filter(CDRRReport.status == status)
    
    # Category filter
    if category:
        query = query.filter(CDRRReport.category == category)
    
    # Get total count
    total = query.count()
    
    # Sorting
    if hasattr(CDRRReport, sort_by):
        order_column = getattr(CDRRReport, sort_by)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(order_column)
    
    # Pagination
    reports = query.offset(skip).limit(limit).all()
    
    return reports, total


def update_cdrr_report(
    db: Session,
    report_id: int,
    report_update: CDRRReportUpdate,
    user_id: int
) -> Optional[CDRRReport]:
    """Update a CDRR report and its nested data"""
    db_report = get_cdrr_report(db, report_id)
    if not db_report:
        return None
    
    # Update main CDRR fields
    main_data = report_update.model_dump(
        exclude={'froo_report', 'cdrr_secondary'},
        exclude_unset=True
    )
    for field, value in main_data.items():
        setattr(db_report, field, value)
    
    db_report.updated_by = user_id
    db_report.updated_at = datetime.utcnow()
    
    # Update FROO report
    if report_update.froo_report is not None:
        if db_report.froo_report:
            # Update existing
            froo_data = report_update.froo_report.model_dump(exclude_unset=True)
            for field, value in froo_data.items():
                setattr(db_report.froo_report, field, value)
            db_report.froo_report.updated_by = user_id
            db_report.froo_report.updated_at = datetime.utcnow()
        else:
            # Create new
            froo_data = report_update.froo_report.model_dump()
            db_froo = FROOReport(
                **froo_data,
                cdrr_report_id=db_report.id,
                created_by=user_id,
                updated_by=user_id
            )
            db.add(db_froo)
    
    # Update CDRR Secondary
    if report_update.cdrr_secondary is not None:
        if db_report.cdrr_secondary:
            # Update existing
            secondary_data = report_update.cdrr_secondary.model_dump(exclude_unset=True)
            for field, value in secondary_data.items():
                setattr(db_report.cdrr_secondary, field, value)
            db_report.cdrr_secondary.updated_by = user_id
            db_report.cdrr_secondary.updated_at = datetime.utcnow()
        else:
            # Create new
            secondary_data = report_update.cdrr_secondary.model_dump()
            db_secondary = CDRRSecondary(
                **secondary_data,
                cdrr_report_id=db_report.id,
                created_by=user_id,
                updated_by=user_id
            )
            db.add(db_secondary)
    
    db.commit()
    db.refresh(db_report)
    return db_report


def delete_cdrr_report(
    db: Session,
    report_id: int,
    user_id: int
) -> bool:
    """Soft delete a CDRR report and its nested data"""
    db_report = get_cdrr_report(db, report_id)
    if not db_report:
        return False
    
    # Soft delete main report
    db_report.is_deleted = True
    db_report.updated_by = user_id
    db_report.updated_at = datetime.utcnow()
    
    # Soft delete nested data
    if db_report.froo_report:
        db_report.froo_report.is_deleted = True
        db_report.froo_report.updated_by = user_id
        db_report.froo_report.updated_at = datetime.utcnow()
    
    if db_report.cdrr_secondary:
        db_report.cdrr_secondary.is_deleted = True
        db_report.cdrr_secondary.updated_by = user_id
        db_report.cdrr_secondary.updated_at = datetime.utcnow()
    
    db.commit()
    return True


def bulk_delete_cdrr_reports(
    db: Session,
    report_ids: list[int],
    user_id: int
) -> int:
    """Bulk soft delete CDRR reports. Returns count of deleted records."""
    # Update main reports
    updated = db.query(CDRRReport).filter(
        and_(
            CDRRReport.id.in_(report_ids),
            CDRRReport.is_deleted == False
        )
    ).update(
        {
            "is_deleted": True,
            "updated_by": user_id,
            "updated_at": datetime.utcnow()
        },
        synchronize_session=False
    )
    
    # Update nested FROO reports
    db.query(FROOReport).filter(
        FROOReport.cdrr_report_id.in_(report_ids)
    ).update(
        {
            "is_deleted": True,
            "updated_by": user_id,
            "updated_at": datetime.utcnow()
        },
        synchronize_session=False
    )
    
    # Update nested CDRR Secondary
    db.query(CDRRSecondary).filter(
        CDRRSecondary.cdrr_report_id.in_(report_ids)
    ).update(
        {
            "is_deleted": True,
            "updated_by": user_id,
            "updated_at": datetime.utcnow()
        },
        synchronize_session=False
    )
    
    db.commit()
    return updated