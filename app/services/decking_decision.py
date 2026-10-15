# app/services/decking_decision.py
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.e_app_history import EAppHistory
from app.models.e_application import EApplication
from app.services.appointment_claim import DEL_LAST_INDEX, DEL_THREAD_OPEN
from app.services.appointment_payment import (
    CLOSED_LAST_INDEX,
    CLOSED_THREAD,
    COMPLETED_STATUS,
)
from app.services.decking_claim import DECKING_STEP

# Must match DECISIONS in CprDetailsModal.jsx
DECISION_FOR_EVALUATION = "For Quality Evaluation"
DECISIONS = {DECISION_FOR_EVALUATION}

# ADAPT: the step that follows an accepted Decking task
EVALUATION_STEP = "Quality Evaluation"
EVALUATION_STATUS = "IN PROGRESS"


def submit_decision(
    db: Session,
    application: EApplication,
    user_uuid: str,
    decision: str,
    remarks: str | None,
    evaluator_uuid: str | None,
) -> dict:
    """Close the decker's task and, if accepted, hand it to the evaluator.

    Does NOT commit. Raises PermissionError if the Decking task is not held
    by the user, and ValueError for invalid input.
    """
    if decision not in DECISIONS:
        raise ValueError("Unknown decision")

    remarks = (remarks or "").strip() or None
    if not evaluator_uuid:
        raise ValueError("Select an evaluator to assign")

    history = (
        db.query(EAppHistory)
        .filter(
            EAppHistory.application_uuid == application.application_uuid,
            EAppHistory.user_uuid == user_uuid,
            EAppHistory.application_step == DECKING_STEP,
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
        .with_for_update()
        .first()
    )
    if not history:
        raise PermissionError("This task is not currently assigned to you")

    history.application_decision = decision
    history.application_remarks = remarks
    history.accomplished_date = func.now()
    history.application_status = COMPLETED_STATUS
    history.del_thread = CLOSED_THREAD
    history.del_last_index = CLOSED_LAST_INDEX

    next_step = None
    if decision == DECISION_FOR_EVALUATION:
        db.add(
            EAppHistory(
                application_uuid=history.application_uuid,
                process_uuid=history.process_uuid,
                reference_number=history.reference_number,
                user_uuid=evaluator_uuid,
                application_step=EVALUATION_STEP,
                application_status=EVALUATION_STATUS,
                start_date=func.now(),
                del_index=(history.del_index or 0) + 1,
                del_previous=history.del_index,
                del_last_index=DEL_LAST_INDEX,
                del_thread=DEL_THREAD_OPEN,
            )
        )
        next_step = EVALUATION_STEP

    return {
        "reference_number": application.reference_number,
        "decision": decision,
        "next_step": next_step,
        "evaluator_uuid": evaluator_uuid if next_step else None,
    }
