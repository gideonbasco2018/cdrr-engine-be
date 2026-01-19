# app/crud/deck.py

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.application_delegation import ApplicationDelegation
from app.schemas.deck import DeckApplicationRequest, BulkDeckApplicationRequest
import logging

logger = logging.getLogger(__name__)

class DeckCRUD:
    """CRUD operations for decking applications"""

    @staticmethod
    def get_delegation_record(db: Session, db_main_id: int) -> Optional[ApplicationDelegation]:
        """Get a single application delegation record by DB_MAIN_ID"""
        try:
            return db.query(ApplicationDelegation).filter(
                ApplicationDelegation.DB_MAIN_ID == db_main_id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching delegation record {db_main_id}: {str(e)}")
            return None

    @staticmethod
    def get_delegation_records(db: Session, db_main_ids: List[int]) -> List[ApplicationDelegation]:
        """Get multiple application delegation records by DB_MAIN_IDs"""
        try:
            return db.query(ApplicationDelegation).filter(
                ApplicationDelegation.DB_MAIN_ID.in_(db_main_ids)
            ).all()
        except Exception as e:
            logger.error(f"Error fetching delegation records: {str(e)}")
            return []

    @staticmethod
    def check_if_already_decked(record: ApplicationDelegation) -> bool:
        """Check if a record already has an evaluator assigned"""
        return bool(record.DB_EVALUATOR and record.DB_EVALUATOR.strip() and record.DB_EVALUATOR != "N/A")

    @staticmethod
    def deck_single_application(
        db: Session,
        db_main_id: int,
        deck_data: DeckApplicationRequest
    ) -> Dict[str, Any]:
        """Deck a single application or update an existing deck"""
        try:
            record = DeckCRUD.get_delegation_record(db, db_main_id)
            if not record:
                return {"success": False, "message": f"Application record with DB_MAIN_ID {db_main_id} not found", "updated_count": 0}

            already_decked = DeckCRUD.check_if_already_decked(record)
            previous_evaluator = record.DB_EVALUATOR if already_decked else None

            # Update record
            record.DB_EVALUATOR = deck_data.evaluator
            record.DB_DECKER = deck_data.decker
            record.DB_DECKER_DECISION = deck_data.deckerDecision
            record.DB_DECKER_REMARKS = deck_data.deckerRemarks or ""
            record.DB_DATE_DECKED = datetime.now()

            # Handle deck end date
            if deck_data.dateDeckedEnd:
                try:
                    record.DB_DATE_DECKED_END = datetime.strptime(deck_data.dateDeckedEnd, "%Y-%m-%d")
                except ValueError:
                    record.DB_DATE_DECKED_END = datetime.now()
                    logger.warning(f"Invalid date format for dateDeckedEnd: {deck_data.dateDeckedEnd}")
            else:
                record.DB_DATE_DECKED_END = datetime.now()

            db.commit()
            db.refresh(record)

            dtn = record.main.DB_DTN if record.main else None
            message = f"Application (DTN: {dtn}) decked successfully"
            if already_decked:
                message += f" (was previously decked by: {previous_evaluator})"

            return {"success": True, "message": message, "updated_count": 1, "record": record}

        except Exception as e:
            db.rollback()
            logger.error(f"Error decking application {db_main_id}: {str(e)}")
            return {"success": False, "message": f"Failed to deck application: {str(e)}", "updated_count": 0}

    @staticmethod
    def bulk_deck_applications(db: Session, bulk_data: BulkDeckApplicationRequest) -> Dict[str, Any]:
        """Deck multiple applications at once"""
        try:
            if not bulk_data.record_ids:
                return {"success": False, "message": "No record IDs provided", "updated_count": 0, "failed_count": 0, "details": []}

            records = DeckCRUD.get_delegation_records(db, bulk_data.record_ids)
            if not records:
                return {"success": False, "message": "No application records found", "updated_count": 0, "failed_count": len(bulk_data.record_ids), "details": []}

            updated_count, failed_count = 0, 0
            details = []

            for record in records:
                try:
                    previous_evaluator = record.DB_EVALUATOR if DeckCRUD.check_if_already_decked(record) else None

                    record.DB_EVALUATOR = bulk_data.evaluator
                    record.DB_DECKER = bulk_data.decker
                    record.DB_DECKER_DECISION = bulk_data.deckerDecision
                    record.DB_DECKER_REMARKS = bulk_data.deckerRemarks or ""
                    record.DB_DATE_DECKED = datetime.now()

                    if bulk_data.dateDeckedEnd:
                        try:
                            record.DB_DATE_DECKED_END = datetime.strptime(bulk_data.dateDeckedEnd, "%Y-%m-%d")
                        except ValueError:
                            record.DB_DATE_DECKED_END = datetime.now()
                            logger.warning(f"Invalid date format for dateDeckedEnd: {bulk_data.dateDeckedEnd}")
                    else:
                        record.DB_DATE_DECKED_END = datetime.now()

                    updated_count += 1
                    details.append({
                        "id": record.DB_MAIN_ID,
                        "dtn": record.main.DB_DTN if record.main else None,
                        "status": "success",
                        "evaluator": bulk_data.evaluator,
                        "previous_evaluator": previous_evaluator
                    })

                except Exception as e:
                    failed_count += 1
                    details.append({
                        "id": getattr(record, "DB_MAIN_ID", "Unknown"),
                        "dtn": getattr(record.main, "DB_DTN", None),
                        "status": "failed",
                        "reason": str(e)
                    })
                    logger.error(f"Error updating record {record.DB_MAIN_ID}: {str(e)}")

            if updated_count > 0:
                db.commit()

            message = f"Successfully decked {updated_count} application(s)"
            if failed_count > 0:
                message += f". {failed_count} failed to update"

            return {"success": updated_count > 0, "message": message, "updated_count": updated_count, "failed_count": failed_count, "details": details}

        except Exception as e:
            db.rollback()
            logger.error(f"Error in bulk deck operation: {str(e)}")
            return {"success": False, "message": f"Bulk deck operation failed: {str(e)}", "updated_count": 0, "failed_count": len(bulk_data.record_ids), "details": []}

    @staticmethod
    def get_decked_applications(db: Session, evaluator: Optional[str] = None, decker: Optional[str] = None,
                                skip: int = 0, limit: int = 100) -> List[ApplicationDelegation]:
        """Get list of decked applications"""
        try:
            query = db.query(ApplicationDelegation).filter(
                ApplicationDelegation.DB_EVALUATOR.isnot(None),
                ApplicationDelegation.DB_EVALUATOR != "",
                ApplicationDelegation.DB_EVALUATOR != "N/A"
            )
            if evaluator:
                query = query.filter(ApplicationDelegation.DB_EVALUATOR == evaluator)
            if decker:
                query = query.filter(ApplicationDelegation.DB_DECKER == decker)
            return query.offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error fetching decked applications: {str(e)}")
            return []

    @staticmethod
    def get_not_decked_applications(db: Session, skip: int = 0, limit: int = 100) -> List[ApplicationDelegation]:
        """Get list of applications that haven't been decked yet"""
        try:
            return db.query(ApplicationDelegation).filter(
                and_(
                    ApplicationDelegation.DB_EVALUATOR.is_(None) |
                    (ApplicationDelegation.DB_EVALUATOR == "") |
                    (ApplicationDelegation.DB_EVALUATOR == "N/A")
                )
            ).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error fetching not decked applications: {str(e)}")
            return []

# Create instance
deck_crud = DeckCRUD()
