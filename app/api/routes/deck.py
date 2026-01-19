# app/routers/deck.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.schemas.deck import (
    DeckApplicationRequest,
    BulkDeckApplicationRequest,
    DeckApplicationResponse,
    BulkDeckResponse,
    DeckRecordDetail
)
from app.crud.deck import deck_crud
from app.core.deps import get_current_active_user
from app.models.user import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/deck",
    tags=["Deck Applications"],
    responses={404: {"description": "Not found"}},
)

# ---------------- Single Deck Endpoint ----------------
@router.patch(
    "/single/{db_main_id}",
    response_model=DeckApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Deck a single application",
    description="Update decking information for a single application"
)
async def deck_single_application(
    db_main_id: int,
    deck_data: DeckApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        result = deck_crud.deck_single_application(db, db_main_id, deck_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return DeckApplicationResponse(
            success=True,
            message=result["message"],
            updated_count=result["updated_count"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in deck_single_application endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while decking the application: {str(e)}"
        )

# ---------------- Bulk Deck Endpoint ----------------
@router.patch(
    "/bulk",
    response_model=BulkDeckResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk deck multiple applications",
    description="Update decking information for multiple applications at once"
)
async def bulk_deck_applications(
    bulk_data: BulkDeckApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        if not bulk_data.record_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No record IDs provided"
            )
        
        if len(bulk_data.record_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deck more than 100 applications at once. Please select fewer records."
            )
        
        result = deck_crud.bulk_deck_applications(db, bulk_data)
        
        return BulkDeckResponse(
            success=result["success"],
            message=result["message"],
            updated_count=result["updated_count"],
            failed_count=result["failed_count"],
            details=result.get("details", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk_deck_applications endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during bulk deck operation: {str(e)}"
        )

# ---------------- Get Decked Applications ----------------
@router.get(
    "/decked",
    response_model=List[DeckRecordDetail],
    summary="Get decked applications",
    description="Retrieve list of applications that have been decked"
)
async def get_decked_applications(
    evaluator: str = None,
    decker: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        records = deck_crud.get_decked_applications(
            db, evaluator=evaluator, decker=decker, skip=skip, limit=limit
        )
        return [
            DeckRecordDetail(
                id=record.DB_MAIN_ID,
                dtn=record.DB_DTN,
                evaluator=record.DB_EVALUATOR,
                decker=record.DB_DECKER,
                deckerDecision=record.DB_DECKER_DECISION,
                deckerRemarks=record.DB_DECKER_REMARKS,
                dateDeck=record.DB_DATE_DECKED,
                dateDeckedEnd=record.DB_DATE_DECKED_END
            )
            for record in records
        ]
    except Exception as e:
        logger.error(f"Error fetching decked applications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch decked applications: {str(e)}"
        )

# ---------------- Get Not Decked Applications ----------------
@router.get(
    "/not-decked",
    response_model=List[DeckRecordDetail],
    summary="Get not decked applications",
    description="Retrieve list of applications that haven't been decked yet"
)
async def get_not_decked_applications(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        records = deck_crud.get_not_decked_applications(db, skip=skip, limit=limit)
        return [
            DeckRecordDetail(
                id=record.DB_MAIN_ID,
                dtn=record.DB_DTN,
                evaluator=record.DB_EVALUATOR,
                decker=record.DB_DECKER,
                deckerDecision=record.DB_DECKER_DECISION,
                deckerRemarks=record.DB_DECKER_REMARKS,
                dateDeck=record.DB_DATE_DECKED,
                dateDeckedEnd=record.DB_DATE_DECKED_END
            )
            for record in records
        ]
    except Exception as e:
        logger.error(f"Error fetching not decked applications: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch not decked applications: {str(e)}"
        )

# ---------------- Get Deck Details for Single Record ----------------
@router.get(
    "/{db_main_id}",
    response_model=DeckRecordDetail,
    summary="Get deck details for a specific record",
    description="Retrieve deck information for a single application"
)
async def get_deck_details(
    db_main_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        record = deck_crud.get_delegation_record(db, db_main_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application record with DB_MAIN_ID {db_main_id} not found"
            )
        return DeckRecordDetail(
            id=record.DB_MAIN_ID,
            dtn=record.DB_DTN,
            evaluator=record.DB_EVALUATOR,
            decker=record.DB_DECKER,
            deckerDecision=record.DB_DECKER_DECISION,
            deckerRemarks=record.DB_DECKER_REMARKS,
            dateDeck=record.DB_DATE_DECKED,
            dateDeckedEnd=record.DB_DATE_DECKED_END
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching deck details for record {db_main_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deck details: {str(e)}"
        )
