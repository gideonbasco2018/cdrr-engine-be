from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from app.models.application_delegation import ApplicationDelegation
from app.schemas.evaluation import (
    EvaluationRequest, 
    BulkEvaluationRequest,
    BulkEvaluationDetail
)
import logging

logger = logging.getLogger(__name__)


class EvaluationCRUD:
    """CRUD operations for application evaluations"""

    @staticmethod
    def get_record(db: Session, db_main_id: int) -> Optional[ApplicationDelegation]:
        """Get a single application record by ID"""
        return db.query(ApplicationDelegation).filter(
            ApplicationDelegation.DB_MAIN_ID == db_main_id
        ).first()

    @staticmethod
    def get_records(db: Session, record_ids: List[int]) -> List[ApplicationDelegation]:
        """Get multiple application records by IDs"""
        return db.query(ApplicationDelegation).filter(
            ApplicationDelegation.DB_MAIN_ID.in_(record_ids)
        ).all()

    @staticmethod
    def is_already_evaluated(record: ApplicationDelegation) -> bool:
        """Check if a record has already been evaluated"""
        return bool(
            record.DB_EVAL_DECISION and
            record.DB_EVAL_DECISION.strip()
        )

    @staticmethod
    def is_decked(record: ApplicationDelegation) -> bool:
        """Check if a record has been decked (assigned to an evaluator)"""
        return bool(record.DB_EVALUATOR and record.DB_EVALUATOR.strip())

    @staticmethod
    def parse_date(date_str: Optional[str]) -> datetime:
        """Parse date string or return current datetime"""
        if date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}, using current datetime")
                return datetime.now()
        return datetime.now()

    @staticmethod
    def update_evaluation_fields(
        record: ApplicationDelegation,
        data: EvaluationRequest
    ) -> None:
        """Update evaluation fields on a record"""
        record.DB_EVALUATOR = data.evaluator
        record.DB_EVAL_DECISION = data.eval_decision
        record.DB_EVAL_REMARKS = data.eval_remarks or ""
        record.DB_DATE_EVAL_END = EvaluationCRUD.parse_date(data.date_eval_end)
        
        # Update checker if provided (can be None to clear)
        record.DB_CHECKER = data.checker

    @staticmethod
    def evaluate_single(
        db: Session,
        db_main_id: int,
        data: EvaluationRequest
    ) -> Dict[str, Any]:
        """
        Evaluate a single application record
        
        Args:
            db: Database session
            db_main_id: Record ID to evaluate
            data: Evaluation data
            
        Returns:
            Dictionary with success status and message
        """
        try:
            record = EvaluationCRUD.get_record(db, db_main_id)
            
            if not record:
                return {
                    "success": False,
                    "message": "Record not found",
                    "updated_count": 0
                }

            # Check if decked first (must be assigned to evaluator)
            if not EvaluationCRUD.is_decked(record):
                return {
                    "success": False,
                    "message": "Application is not yet decked (not assigned to evaluator)",
                    "updated_count": 0
                }

            # Update evaluation fields
            EvaluationCRUD.update_evaluation_fields(record, data)

            db.commit()
            db.refresh(record)

            logger.info(f"Successfully evaluated record {db_main_id} by {data.evaluator}")

            return {
                "success": True,
                "message": "Application evaluated successfully",
                "updated_count": 1
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Evaluation error for record {db_main_id}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Evaluation failed: {str(e)}",
                "updated_count": 0
            }

    @staticmethod
    def bulk_evaluate(
        db: Session,
        data: BulkEvaluationRequest
    ) -> Dict[str, Any]:
        """
        Evaluate multiple application records in bulk
        
        Args:
            db: Database session
            data: Bulk evaluation data including record IDs
            
        Returns:
            Dictionary with success status, counts, and details
        """
        updated_count = 0
        failed_count = 0
        details: List[BulkEvaluationDetail] = []

        try:
            # Fetch all records
            records = EvaluationCRUD.get_records(db, data.record_ids)
            found_ids: Set[int] = {r.DB_MAIN_ID for r in records}
            
            # Check for missing records
            missing_ids = set(data.record_ids) - found_ids
            for missing_id in missing_ids:
                failed_count += 1
                details.append(BulkEvaluationDetail(
                    id=missing_id,
                    status="failed",
                    reason="Record not found"
                ))

            # Process each found record
            for record in records:
                try:
                    # Validate: must be decked
                    if not EvaluationCRUD.is_decked(record):
                        failed_count += 1
                        details.append(BulkEvaluationDetail(
                            id=record.DB_MAIN_ID,
                            status="failed",
                            reason="Application is not yet decked"
                        ))
                        continue

                    # Update evaluation fields
                    record.DB_EVALUATOR = data.evaluator
                    record.DB_EVAL_DECISION = data.eval_decision
                    record.DB_EVAL_REMARKS = data.eval_remarks or ""
                    record.DB_DATE_EVAL_END = EvaluationCRUD.parse_date(data.date_eval_end)
                    
                    # Update checker (can be None to clear)
                    record.DB_CHECKER = data.checker

                    updated_count += 1
                    details.append(BulkEvaluationDetail(
                        id=record.DB_MAIN_ID,
                        status="success",
                        reason=None
                    ))

                except Exception as e:
                    failed_count += 1
                    details.append(BulkEvaluationDetail(
                        id=record.DB_MAIN_ID,
                        status="failed",
                        reason=str(e)
                    ))
                    logger.error(f"Error processing record {record.DB_MAIN_ID}: {str(e)}")

            # Commit all changes at once
            if updated_count > 0:
                db.commit()
                logger.info(f"Bulk evaluation completed: {updated_count} updated, {failed_count} failed")

            return {
                "success": updated_count > 0,
                "message": f"Evaluated {updated_count} record(s), {failed_count} failed",
                "updated_count": updated_count,
                "failed_count": failed_count,
                "details": details
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Bulk evaluation error: {str(e)}", exc_info=True)
            
            # Mark all as failed if transaction fails
            return {
                "success": False,
                "message": f"Bulk evaluation failed: {str(e)}",
                "updated_count": 0,
                "failed_count": len(data.record_ids),
                "details": [
                    BulkEvaluationDetail(
                        id=rid,
                        status="failed",
                        reason="Transaction failed"
                    ) for rid in data.record_ids
                ]
            }


# Singleton instance
evaluation_crud = EvaluationCRUD()