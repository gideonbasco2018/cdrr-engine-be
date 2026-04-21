from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.schemas.applications import ApplicationItem, ApplicationsResponse
import app.crud.applications as crud_my_apps

router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)


@router.get("/", response_model=ApplicationsResponse)
def get_my_applications(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Returns all applications assigned to the current logged-in user.

    Logic:
    - Filters application_logs by user_id = current_user.id
    - Filters del_thread = 'close'
    - Per application (main_db_id), keeps only the row with
      the highest del_index (latest step in the thread)
    - Joins main_db to return product/establishment details
    """
    try:
        rows = crud_my_apps.get_my_applications(db, user_id=current_user.id)

        items = [
            ApplicationItem(
                # log fields
                log_id=log.id,
                main_db_id=log.main_db_id,
                del_index=log.del_index,
                del_thread=log.del_thread,
                application_step=log.application_step,
                application_status=log.application_status,
                application_decision=log.application_decision,
                application_remarks=log.application_remarks,
                created_at=log.created_at,
                updated_at=log.updated_at,
                # main_db fields
                dtn=main.DB_DTN,
                est_cat=main.DB_EST_CAT,
                est_lto_comp=main.DB_EST_LTO_COMP,
                prod_br_name=main.DB_PROD_BR_NAME,
                prod_gen_name=main.DB_PROD_GEN_NAME,
                app_status=main.DB_APP_STATUS,
            )
            for log, main in rows
        ]

        return ApplicationsResponse(total=len(items), items=items)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch applications: {str(e)}",
        )