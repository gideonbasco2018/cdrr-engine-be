from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.evaluation import (
    EvaluationRequest,
    BulkEvaluationRequest,
    EvaluationResponse,
    BulkEvaluationResponse
)
from app.crud.evaluation import evaluation_crud
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/evaluation",
    tags=["Evaluation"],
)


def check_evaluation_permission(current_user: User) -> None:
    """
    Check if the current user has permission to evaluate applications
    
    Args:
        current_user: The authenticated user
        
    Raises:
        HTTPException: If user doesn't have evaluation permissions
    """
    # Adjust this based on your permission system
    # Examples:
    # - if not current_user.can_evaluate:
    # - if current_user.role not in ["evaluator", "admin"]:
    # - if not hasattr(current_user, "evaluation_permission") or not current_user.evaluation_permission:
    
    # For now, assuming all active users can evaluate
    # Remove this pass and implement your actual permission check
    pass


@router.patch(
    "/single/{db_main_id}",
    response_model=EvaluationResponse,
    summary="Evaluate a single application",
    description="Evaluate a single application by its ID. The application must be decked (assigned) before evaluation.",
    responses={
        200: {
            "description": "Application evaluated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Application evaluated successfully",
                        "updated_count": 1
                    }
                }
            }
        },
        400: {
            "description": "Bad request - validation error or business rule violation",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Application is not yet decked (not assigned to evaluator)"
                    }
                }
            }
        },
        403: {"description": "Forbidden - user doesn't have evaluation permissions"},
        404: {"description": "Record not found"}
    }
)
async def evaluate_single_application(
    db_main_id: int,
    data: EvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> EvaluationResponse:
    """
    Evaluate a single application
    
    Args:
        db_main_id: The ID of the application to evaluate
        data: Evaluation data (decision, remarks, etc.)
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        EvaluationResponse with success status and message
    """
    # Check permissions
    check_evaluation_permission(current_user)
    
    # Perform evaluation
    result = evaluation_crud.evaluate_single(db, db_main_id, data)

    # Handle different failure cases
    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["message"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )

    logger.info(f"User {current_user.username} evaluated application {db_main_id}")
    
    return EvaluationResponse(**result)


@router.patch(
    "/bulk",
    response_model=BulkEvaluationResponse,
    summary="Evaluate multiple applications in bulk",
    description="Evaluate multiple applications at once. Returns detailed status for each record.",
    responses={
        200: {
            "description": "Bulk evaluation completed (may include partial failures)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Evaluated 8 record(s), 2 failed",
                        "updated_count": 8,
                        "failed_count": 2,
                        "details": [
                            {"id": 1, "status": "success", "reason": None},
                            {"id": 2, "status": "failed", "reason": "Application is not yet decked"}
                        ]
                    }
                }
            }
        },
        400: {"description": "Bad request - validation error"},
        403: {"description": "Forbidden - user doesn't have evaluation permissions"}
    }
)
async def bulk_evaluate_applications(
    data: BulkEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> BulkEvaluationResponse:
    """
    Evaluate multiple applications in bulk
    
    Args:
        data: Bulk evaluation data including list of record IDs
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        BulkEvaluationResponse with counts and detailed status for each record
    """
    # Check permissions
    check_evaluation_permission(current_user)
    
    # Perform bulk evaluation
    result = evaluation_crud.bulk_evaluate(db, data)
    
    logger.info(
        f"User {current_user.username} bulk evaluated {result['updated_count']} applications "
        f"({result['failed_count']} failed)"
    )
    
    return BulkEvaluationResponse(**result)


@router.get(
    "/status/{db_main_id}",
    summary="Get evaluation status of an application",
    description="Check if an application has been evaluated and get evaluation details"
)
async def get_evaluation_status(
    db_main_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the evaluation status of an application
    
    Args:
        db_main_id: The ID of the application
        db: Database session
        current_user: Currently authenticated user
        
    Returns:
        Evaluation status and details
    """
    record = evaluation_crud.get_record(db, db_main_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found"
        )
    
    return {
        "id": record.DB_MAIN_ID,
        "is_decked": evaluation_crud.is_decked(record),
        "is_evaluated": evaluation_crud.is_already_evaluated(record),
        "evaluator": record.DB_EVALUATOR,
        "eval_decision": record.DB_EVAL_DECISION,
        "eval_remarks": record.DB_EVAL_REMARKS,
        "date_eval_end": record.DB_DATE_EVAL_END,
        "checker": record.DB_CHECKER
    }