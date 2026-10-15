# app/services/decking_claim.py
from sqlalchemy.orm import Session

from app.models.e_app_history import EAppHistory
from app.services.appointment_claim import DEL_LAST_INDEX, DEL_THREAD_OPEN
from app.services.appointment_payment import NEXT_STEP as DECKING_STEP


def claim_decking_task(db: Session, application_uuid: str, user_uuid: str) -> bool:
    """Assign an unassigned Decking task to the user.

    One atomic UPDATE: only a row that is still unassigned gets the user,
    so two deckers claiming at the same moment cannot both win.
    Does NOT commit. Returns True if this user got the task.
    """
    updated = (
        db.query(EAppHistory)
        .filter(
            EAppHistory.application_uuid == application_uuid,
            EAppHistory.application_step == DECKING_STEP,
            EAppHistory.user_uuid.is_(None),
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
        .update({"user_uuid": user_uuid}, synchronize_session=False)
    )
    return updated == 1
