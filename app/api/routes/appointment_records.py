# app/api/routes/appointment_records.py
from typing import Literal
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.services.drive_files import extract_folder_id, list_folder, get_file_bytes

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.appointment_db import get_appointment_db
from app.core.deps import get_current_active_user
from app.db.session import get_db
from app.models.appointment_record import AppointmentRecord
from app.models.e_app_history import EAppHistory
from app.models.e_application import EApplication
from app.models.e_process import EProcess
from app.schemas.appointment_record import (
    AppointmentRecordDetail,
    AppointmentRecordPage,
    ClaimedApplicationDetail,
    ClaimRequest,
    ClaimResult,
    DeckingDecisionRequest,
    DeckingDecisionResult,
    EvaluatorOut,
    MyTaskItem,
    PostPaymentRequest,
    PostPaymentResult,
)
from app.services.appointment_claim import (
    DEL_LAST_INDEX,
    DEL_THREAD_OPEN,
    claim_record,
    is_claimed,
)
from app.models.user import User  # ADAPT: real module path of your User model
from app.services.decking_claim import DECKING_STEP, claim_decking_task
from app.services.decking_decision import submit_decision
from app.services.appointment_payment import post_payments
from app.services.workflow_roles import (
    ROLE_CASHIER,
    ROLE_DECKER,
    ROLE_EVALUATOR,
    get_role_group_ids,
    user_has_role,
)
from app.models.group import Group  # ADAPT: real module path of your Group model

logger = logging.getLogger(__name__)


def get_user_group_ids(user) -> list[int]:
    # ADAPT: use the real relationship/attribute name on your User model
    return [g.id for g in (getattr(user, "groups", None) or [])]


def is_decker(db, user) -> bool:
    return user_has_role(db, user, ROLE_DECKER)


def require_decker(db, user) -> None:
    if not is_decker(db, user):
        raise HTTPException(
            status_code=403, detail="Only deckers can access the Decking pool"
        )


def to_task_item(history, app, process_code) -> dict:
    return {
        "application_uuid": app.application_uuid,
        "process_code": process_code,
        "reference_number": app.reference_number,
        "activity": app.activity,
        "application_type": app.application_type,
        "applicant_company": app.applicant_company,
        "application_step": history.application_step,
        "application_status": history.application_status,
        "application_remarks": history.application_remarks,
        "priority": history.priority,
        "step_duedate": history.step_duedate,
        "deadline_date": history.deadline_date,
        "start_date": history.start_date,
        "updated_at": history.updated_at,
    }


def _get_accessible_application(internal_db, reference_no, current_user):
    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    has_access = (
        internal_db.query(EAppHistory.history_uuid)
        .filter(
            EAppHistory.application_uuid == application.application_uuid,
            EAppHistory.user_uuid == current_user.user_uuid,
        )
        .first()
        is not None
    )
    if not has_access:
        raise HTTPException(
            status_code=403, detail="You do not have access to this application"
        )
    root_id = extract_folder_id(application.drive_link)  # ADAPT: column name
    return application, root_id


router = APIRouter(
    prefix="/api/appointment-records",
    tags=["Appointment Records"],
    dependencies=[Depends(get_current_active_user)],
)


@router.get("", response_model=AppointmentRecordPage)
@router.get("/", response_model=AppointmentRecordPage, include_in_schema=False)
def list_appointment_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    search: str | None = None,
    unclaimed_only: bool = False,
    db: Session = Depends(get_appointment_db),
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    # The unclaimed pool is for cashiers only
    if unclaimed_only and not user_has_role(internal_db, current_user, ROLE_CASHIER):
        raise HTTPException(
            status_code=403, detail="Only cashiers can view the unclaimed pool"
        )

    query = db.query(AppointmentRecord)

    if status:
        query = query.filter(AppointmentRecord.status == status)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                AppointmentRecord.reference_no.ilike(like),
                AppointmentRecord.company_name.ilike(like),
                AppointmentRecord.activity.ilike(like),
            )
        )

    if unclaimed_only:
        claimed = [
            row[0]
            for row in internal_db.query(EApplication.reference_number)
            .filter(EApplication.reference_number.isnot(None))
            .all()
        ]
        if claimed:
            query = query.filter(AppointmentRecord.reference_no.notin_(claimed))

    total = query.count()
    items = (
        query.order_by(AppointmentRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/claim", response_model=list[ClaimResult])
def claim_appointment_records(
    payload: ClaimRequest,
    db: Session = Depends(get_appointment_db),
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    if not user_has_role(internal_db, current_user, ROLE_CASHIER):
        raise HTTPException(status_code=403, detail="Only cashiers can claim tasks")

    results: list[ClaimResult] = []

    for reference_no in dict.fromkeys(payload.reference_numbers):  # de-duplicate
        if is_claimed(internal_db, reference_no):
            results.append(
                ClaimResult(reference_no=reference_no, result="already_claimed")
            )
            continue

        record = (
            db.query(AppointmentRecord)
            .filter(
                AppointmentRecord.reference_no == reference_no,
                AppointmentRecord.status == "Accepted",
            )
            .first()
        )
        if not record:
            results.append(ClaimResult(reference_no=reference_no, result="not_found"))
            continue

        try:
            claim_record(
                internal_db, record, current_user.user_uuid
            )  # ADAPT: attribute name
            internal_db.commit()
            results.append(ClaimResult(reference_no=reference_no, result="claimed"))
        except IntegrityError:
            # another user claimed it at the same moment (unique reference_number)
            internal_db.rollback()
            results.append(
                ClaimResult(reference_no=reference_no, result="already_claimed")
            )
        except ValueError as err:
            internal_db.rollback()
            results.append(
                ClaimResult(reference_no=reference_no, result="failed", detail=str(err))
            )
        except Exception:
            # Log the real error server-side, but don't leak it to the client and
            # don't abort the batch: earlier references may already be committed.
            internal_db.rollback()
            logger.exception("Unexpected error claiming %s", reference_no)
            results.append(
                ClaimResult(
                    reference_no=reference_no,
                    result="failed",
                    detail="Unexpected error while claiming this record",
                )
            )

    return results


@router.get("/my-access")
def get_my_access(
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    return {
        "group_ids": get_user_group_ids(current_user),
        "is_cashier": user_has_role(internal_db, current_user, ROLE_CASHIER),
        "is_decker": is_decker(internal_db, current_user),
    }


@router.get("/my-tasks", response_model=list[MyTaskItem])
def list_my_tasks(
    scope: Literal["open", "processed"] = "open",
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    query = (
        internal_db.query(EAppHistory, EApplication, EProcess.process_code)
        .join(
            EApplication,
            EApplication.application_uuid == EAppHistory.application_uuid,
        )
        .join(EProcess, EProcess.process_uuid == EAppHistory.process_uuid)
        .filter(EAppHistory.user_uuid == current_user.user_uuid)
    )
    if scope == "processed":
        query = query.filter(
            EAppHistory.del_thread == "Closed",
            EAppHistory.del_last_index == 0,
        ).order_by(EAppHistory.accomplished_date.desc())
    else:
        query = query.filter(
            EAppHistory.del_thread == "Open",
            EAppHistory.del_last_index == 1,
        ).order_by(EAppHistory.start_date.desc())

    return [
        to_task_item(history, app, process_code)
        for history, app, process_code in query.all()
    ]


@router.get("/decking/unclaimed", response_model=list[MyTaskItem])
def list_decking_unclaimed(
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_decker(internal_db, current_user)
    rows = (
        internal_db.query(EAppHistory, EApplication, EProcess.process_code)
        .join(
            EApplication,
            EApplication.application_uuid == EAppHistory.application_uuid,
        )
        .join(EProcess, EProcess.process_uuid == EAppHistory.process_uuid)
        .filter(
            EAppHistory.application_step == DECKING_STEP,
            EAppHistory.user_uuid.is_(None),
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
        .order_by(EAppHistory.start_date.asc())
        .all()
    )
    return [to_task_item(history, app, code) for history, app, code in rows]


@router.post("/decking/claim", response_model=list[ClaimResult])
def claim_decking_tasks(
    payload: ClaimRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_decker(internal_db, current_user)
    results: list[ClaimResult] = []

    for reference_no in dict.fromkeys(payload.reference_numbers):  # de-duplicate
        application = (
            internal_db.query(EApplication)
            .filter(EApplication.reference_number == reference_no)
            .first()
        )
        if not application:
            results.append(ClaimResult(reference_no=reference_no, result="not_found"))
            continue

        try:
            claimed = claim_decking_task(
                internal_db, application.application_uuid, current_user.user_uuid
            )
            internal_db.commit()
        except Exception:
            internal_db.rollback()
            logger.exception("Unexpected error claiming decking task %s", reference_no)
            results.append(
                ClaimResult(
                    reference_no=reference_no,
                    result="failed",
                    detail="Unexpected error while claiming this task",
                )
            )
            continue

        results.append(
            ClaimResult(
                reference_no=reference_no,
                result="claimed" if claimed else "already_claimed",
            )
        )

    return results


def _evaluators_query(internal_db: Session):
    # ADAPT: attribute names (is_active, groups, first_name, surname)
    return internal_db.query(User).filter(
        User.is_active.is_(True),
        User.groups.any(Group.id.in_(get_role_group_ids(internal_db, ROLE_EVALUATOR))),
    )


@router.get("/decking/evaluators", response_model=list[EvaluatorOut])
def list_evaluators(
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_decker(internal_db, current_user)
    users = _evaluators_query(internal_db).order_by(User.first_name, User.surname).all()
    return [
        {
            "user_uuid": u.user_uuid,
            "name": f"{u.first_name or ''} {u.surname or ''}".strip(),
        }
        for u in users
    ]


@router.post(
    "/claimed/{reference_no}/decking-decision",
    response_model=DeckingDecisionResult,
)
def post_decking_decision(
    reference_no: str,
    payload: DeckingDecisionRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_decker(internal_db, current_user)

    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # the assigned evaluator must really be an active evaluator
    if payload.evaluator_uuid:
        is_valid = (
            _evaluators_query(internal_db)
            .filter(User.user_uuid == payload.evaluator_uuid)
            .first()
            is not None
        )
        if not is_valid:
            raise HTTPException(status_code=422, detail="Invalid evaluator selected")

    try:
        result = submit_decision(
            internal_db,
            application,
            current_user.user_uuid,
            payload.decision,
            payload.remarks,
            payload.evaluator_uuid,
        )
        internal_db.commit()
    except PermissionError as err:
        internal_db.rollback()
        raise HTTPException(status_code=403, detail=str(err))
    except ValueError as err:
        internal_db.rollback()
        raise HTTPException(status_code=422, detail=str(err))
    except Exception:
        internal_db.rollback()
        logger.exception(
            "Unexpected error saving decking decision for %s", reference_no
        )
        raise HTTPException(
            status_code=500, detail="Unexpected error while saving the decision"
        )

    return result


@router.get("/claimed/{reference_no}", response_model=ClaimedApplicationDetail)
def get_claimed_application(
    reference_no: str,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # only users who have worked on this application can view it
    has_access = (
        internal_db.query(EAppHistory.history_uuid)
        .filter(
            EAppHistory.application_uuid == application.application_uuid,
            EAppHistory.user_uuid == current_user.user_uuid,
        )
        .first()
        is not None
    )
    if not has_access:
        raise HTTPException(
            status_code=403, detail="You do not have access to this application"
        )

    return application


@router.post("/claimed/{reference_no}/payments", response_model=PostPaymentResult)
def post_claimed_payments(
    reference_no: str,
    payload: PostPaymentRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        result = post_payments(
            internal_db,
            application,
            current_user.user_uuid,
            payload.payments,
            payload.remarks,
        )
        internal_db.commit()
    except PermissionError as err:
        internal_db.rollback()
        raise HTTPException(status_code=403, detail=str(err))
    except ValueError as err:
        internal_db.rollback()
        raise HTTPException(status_code=409, detail=str(err))
    except Exception:
        internal_db.rollback()
        logger.exception("Unexpected error posting payment for %s", reference_no)
        raise HTTPException(
            status_code=500, detail="Unexpected error while posting the payment"
        )

    return result


@router.get("/{reference_no}", response_model=AppointmentRecordDetail)
def get_appointment_record(
    reference_no: str,
    db: Session = Depends(get_appointment_db),
):
    record = (
        db.query(AppointmentRecord)
        .filter(AppointmentRecord.reference_no == reference_no)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Appointment record not found")
    return record


@router.get("/claimed/{reference_no}/drive-files")
def list_drive_files(
    reference_no: str,
    folder_id: str | None = None,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    _, root_id = _get_accessible_application(internal_db, reference_no, current_user)
    if not root_id:
        return {"root_id": None, "items": []}
    try:
        return {"root_id": root_id, "items": list_folder(root_id, folder_id)}
    except PermissionError as err:
        raise HTTPException(status_code=403, detail=str(err))
    except Exception:
        logger.exception("Drive list failed for %s", reference_no)
        raise HTTPException(
            status_code=502, detail="Could not read the Google Drive folder"
        )


@router.get("/claimed/{reference_no}/drive-files/{file_id}/content")
def get_drive_file_content(
    reference_no: str,
    file_id: str,
    download: bool = False,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    _, root_id = _get_accessible_application(internal_db, reference_no, current_user)
    if not root_id:
        raise HTTPException(
            status_code=404, detail="No Drive folder for this application"
        )
    try:
        content, mime, name = get_file_bytes(root_id, file_id)
    except PermissionError as err:
        raise HTTPException(status_code=403, detail=str(err))
    except Exception:
        logger.exception("Drive download failed for %s/%s", reference_no, file_id)
        raise HTTPException(
            status_code=502, detail="Could not read the file from Google Drive"
        )
    disposition = "attachment" if download else "inline"
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'{disposition}; filename="{name}"'},
    )
