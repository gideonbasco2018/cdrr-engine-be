# app/api/routes/appointment_records.py
from typing import Literal
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.services.drive_files import extract_folder_id, list_folder, get_file_bytes

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

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
    NodExtendRequest,
    NodOut,
    NodReceiveRequest,
    WorksheetIn,
    WorksheetResponse,
    PostPaymentRequest,
    PostPaymentResult,
    StepActionOut,
    StepDecisionRequest,
    StepDecisionResult,
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
    ROLE_FGMP_EVALUATOR,
    get_role_group_ids,
    user_has_role,
)
from app.models.group import Group  # ADAPT: real module path of your Group model
from app.models.e_app_notice_of_deficiency import EAppNoticeOfDeficiency
from app.services.fgmp_nod import extend_nod, list_nods, receive_documents
from app.services.fgmp_worksheet import build_out as build_worksheet_out
from app.services.fgmp_worksheet import latest_row as latest_worksheet
from app.services.fgmp_worksheet import save_draft as save_worksheet_draft
from app.services.fgmp_workflow import (
    CERTIFICATE_ISSUANCE_TYPES,
    EVALUATOR_STEP,
    STEP_GROUP_IDS,
    TYPE_OF_ISSUANCE_OPTIONS,
    TYPE_OF_ISSUANCE_STEP,
    actions_for_step,
    next_certificate_number,
    open_task_held_by,
    resolve_next_step,
    submit_step_decision,
)

logger = logging.getLogger(__name__)

# Only the process filter below still uses fixed group IDs. Everything else
# goes through the role lookup in app/services/workflow_roles.py.
DECKER_GROUP_ID = 2

# FGMP runs its own workflow with its own groups, so an FGMP decker is not a
# CPR decker and vice versa (see the `groups` table).
FGMP_PROCESS_CODE = "FGMP"
FGMP_DECKER_GROUP_ID = 30
# Which group handles each workflow step lives with the routing table, in
# app/services/fgmp_workflow.py (STEP_GROUP_IDS).


def get_user_group_ids(user) -> list[int]:
    # ADAPT: use the real relationship/attribute name on your User model
    return [g.id for g in (getattr(user, "groups", None) or [])]


def is_decker(db, user) -> bool:
    # FGMP deckers (group 30) count too; the rest comes from the role lookup
    return user_has_role(db, user, ROLE_DECKER) or (
        FGMP_DECKER_GROUP_ID in get_user_group_ids(user)
    )


def may_deck_process(user, process_code: str | None) -> bool:
    """Whether this decker handles that process.

    An FGMP decker only sees Foreign GMP applications, a CPR decker only sees
    the rest, and someone in both groups sees both.
    """
    group_ids = get_user_group_ids(user)
    sees_fgmp = FGMP_DECKER_GROUP_ID in group_ids
    sees_others = DECKER_GROUP_ID in group_ids
    if sees_fgmp and not sees_others:
        return process_code == FGMP_PROCESS_CODE
    if sees_others and not sees_fgmp:
        return process_code != FGMP_PROCESS_CODE
    return True


def limit_to_decker_processes(query, user):
    """Same rule as may_deck_process, applied to a Decking query."""
    group_ids = get_user_group_ids(user)
    sees_fgmp = FGMP_DECKER_GROUP_ID in group_ids
    sees_others = DECKER_GROUP_ID in group_ids
    if sees_fgmp and not sees_others:
        return query.filter(EProcess.process_code == FGMP_PROCESS_CODE)
    if sees_others and not sees_fgmp:
        return query.filter(EProcess.process_code != FGMP_PROCESS_CODE)
    return query


# Acting on a workflow step is guarded by "do you hold this task?" rather than
# by group, so the same check works for every step (see _require_step_holder).


def require_decker(db, user) -> None:
    if not is_decker(db, user):
        raise HTTPException(
            status_code=403, detail="Only deckers can access the Decking pool"
        )


def to_task_item(history, app, process_code, came_from=None) -> dict:
    """`came_from` is the step that handed this task over (the row at
    history.del_previous), so an open task can say how it arrived: endorsed,
    returned, or sent back for compliance."""
    # FGMP applications carry their own details on a 1:1 child row
    fgmp = getattr(app, "fgmp", None)
    return {
        "dtn": fgmp.dtn if fgmp else None,
        "category": fgmp.category if fgmp else None,
        "foreign_manufacturer": fgmp.foreign_manufacturer if fgmp else None,
        "type_of_issuance": fgmp.type_of_issuance if fgmp else None,
        "application_uuid": app.application_uuid,
        "process_code": process_code,
        "reference_number": app.reference_number,
        "activity": app.activity,
        "application_type": app.application_type,
        "applicant_company": app.applicant_company,
        "application_step": history.application_step,
        "application_status": history.application_status,
        "application_remarks": history.application_remarks,
        "application_decision": history.application_decision,
        "from_decision": came_from[0] if came_from else None,
        "from_step": came_from[1] if came_from else None,
        "accomplished_date": history.accomplished_date,
        "del_index": history.del_index,
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
    # The step that handed this task over, so the screen can tell an endorsed
    # application from one returned or sent back for compliance.
    previous = aliased(EAppHistory)
    query = (
        internal_db.query(
            EAppHistory,
            EApplication,
            EProcess.process_code,
            previous.application_decision,
            previous.application_step,
        )
        .join(
            EApplication,
            EApplication.application_uuid == EAppHistory.application_uuid,
        )
        .join(EProcess, EProcess.process_uuid == EAppHistory.process_uuid)
        .outerjoin(
            previous,
            and_(
                previous.application_uuid == EAppHistory.application_uuid,
                previous.del_index == EAppHistory.del_previous,
            ),
        )
        .options(joinedload(EApplication.fgmp))
        .filter(EAppHistory.user_uuid == current_user.user_uuid)
    )
    if scope == "processed":
        query = query.filter(
            EAppHistory.del_thread == "Closed",
            EAppHistory.del_last_index == 0,
        ).order_by(
            EAppHistory.accomplished_date.desc(),
            EAppHistory.del_index.desc(),
        )
    else:
        query = query.filter(
            EAppHistory.del_thread == "Open",
            EAppHistory.del_last_index == 1,
        ).order_by(EAppHistory.start_date.desc())

    return [
        to_task_item(history, app, process_code, (from_decision, from_step))
        for history, app, process_code, from_decision, from_step in query.all()
    ]


@router.get("/decking/unclaimed", response_model=list[MyTaskItem])
def list_decking_unclaimed(
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_decker(internal_db, current_user)
    query = (
        internal_db.query(EAppHistory, EApplication, EProcess.process_code)
        .join(
            EApplication,
            EApplication.application_uuid == EAppHistory.application_uuid,
        )
        .join(EProcess, EProcess.process_uuid == EAppHistory.process_uuid)
        .options(joinedload(EApplication.fgmp))
        .filter(
            EAppHistory.application_step == DECKING_STEP,
            EAppHistory.user_uuid.is_(None),
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
    )
    # An FGMP decker only sees Foreign GMP, a CPR decker only sees the rest
    query = limit_to_decker_processes(query, current_user)
    rows = query.order_by(EAppHistory.start_date.asc()).all()
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

        # Same rule as the pool above: a decker cannot claim another
        # workflow's application by passing its reference number directly.
        process_code = (
            application.app_ref.process.process_code
            if application.app_ref and application.app_ref.process
            else None
        )
        if not may_deck_process(current_user, process_code):
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


def _group_members_query(internal_db: Session, group_id: int):
    # ADAPT: attribute names (is_active, groups, first_name, surname)
    return internal_db.query(User).filter(
        User.is_active.is_(True),
        User.groups.any(id=group_id),
    )


def _evaluator_group_ids(internal_db: Session, user) -> set[int]:
    """The groups whose members this decker may hand an application to.

    Same split as the decking pool: an FGMP decker gets the FGMP evaluators, a
    CPR decker the usual evaluators, and a decker for both gets both lists.
    """
    group_ids = get_user_group_ids(user)
    sees_fgmp = FGMP_DECKER_GROUP_ID in group_ids
    sees_others = DECKER_GROUP_ID in group_ids
    # If an admin has not set the FGMP role yet, fall back to the evaluator
    # group the FGMP workflow itself uses.
    fgmp = get_role_group_ids(internal_db, ROLE_FGMP_EVALUATOR) or {
        STEP_GROUP_IDS[EVALUATOR_STEP]
    }
    usual = get_role_group_ids(internal_db, ROLE_EVALUATOR)
    if sees_fgmp and not sees_others:
        return fgmp
    if sees_others and not sees_fgmp:
        return usual
    return fgmp | usual


def _evaluators_query(internal_db: Session, user):
    return internal_db.query(User).filter(
        User.is_active.is_(True),
        User.groups.any(Group.id.in_(_evaluator_group_ids(internal_db, user))),
    )


def _as_assignee_list(users) -> list[dict]:
    return [
        {
            "user_uuid": u.user_uuid,
            "name": f"{u.first_name or ''} {u.surname or ''}".strip(),
        }
        for u in users
    ]


@router.get("/decking/evaluators", response_model=list[EvaluatorOut])
def list_evaluators(
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    require_decker(internal_db, current_user)
    users = (
        _evaluators_query(internal_db, current_user)
        .order_by(User.first_name, User.surname)
        .all()
    )
    return _as_assignee_list(users)


# ── FGMP workflow steps (Quality Evaluation onwards) ──────────────────────
# The actions, where each leads and which group handles each step all live in
# app/services/fgmp_workflow.py. These endpoints work for every step, so a new
# step needs no new endpoint.
def _require_step_holder(internal_db: Session, reference_no: str, user):
    """Load the application and the caller's own open task on it."""
    application = (
        internal_db.query(EApplication)
        .filter(EApplication.reference_number == reference_no)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    task = open_task_held_by(internal_db, application.application_uuid, user.user_uuid)
    if not task:
        raise HTTPException(
            status_code=403, detail="This task is not currently assigned to you"
        )
    return application, task


@router.get("/claimed/{reference_no}/step-actions", response_model=list[StepActionOut])
def list_step_actions(
    reference_no: str,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """What the holder of this task may do at the step it is on."""
    _, task = _require_step_holder(internal_db, reference_no, current_user)
    return actions_for_step(task.application_step)


@router.get("/workflow/issuance-types", response_model=list[str])
def list_issuance_types(current_user=Depends(get_current_active_user)):
    """What may be issued, for the step that decides it."""
    return TYPE_OF_ISSUANCE_OPTIONS


@router.get("/workflow/next-certificate-number")
def peek_next_certificate_number(
    type_of_issuance: str = Query(..., description="The type being considered"),
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The number the next certificate would get, for the preview.

    Nothing is reserved — the number is only taken when the decision is
    submitted, so a certificate issued elsewhere first would take this one.
    """
    if type_of_issuance not in CERTIFICATE_ISSUANCE_TYPES:
        return {"certificate_number": None}
    return {"certificate_number": next_certificate_number(internal_db)}


@router.get("/workflow/assignees", response_model=list[EvaluatorOut])
def list_step_assignees(
    next_step: str = Query(..., description="The step the application is going to"),
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    group_id = STEP_GROUP_IDS.get(next_step)
    if group_id is None:
        raise HTTPException(
            status_code=422, detail=f"Nobody is assignable for step '{next_step}'"
        )
    users = (
        _group_members_query(internal_db, group_id)
        .order_by(User.first_name, User.surname)
        .all()
    )
    return _as_assignee_list(users)


@router.post(
    "/claimed/{reference_no}/step-decision",
    response_model=StepDecisionResult,
)
def post_step_decision(
    reference_no: str,
    payload: StepDecisionRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    application, task = _require_step_holder(internal_db, reference_no, current_user)

    # the person picked must really belong to the next step's group
    _, next_step = resolve_next_step(task.application_step, payload.decision)
    group_id = STEP_GROUP_IDS.get(next_step) if next_step else None
    if payload.assignee_uuid and group_id is not None:
        is_valid = (
            _group_members_query(internal_db, group_id)
            .filter(User.user_uuid == payload.assignee_uuid)
            .first()
            is not None
        )
        if not is_valid:
            raise HTTPException(
                status_code=422, detail=f"Invalid {next_step} selected"
            )

    try:
        result = submit_step_decision(
            internal_db,
            application,
            current_user.user_uuid,
            payload.decision,
            payload.remarks,
            payload.assignee_uuid,
            payload.type_of_issuance,
            payload.nod.model_dump() if payload.nod else None,
            payload.worksheet.model_dump() if payload.worksheet else None,
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
        logger.exception("Unexpected error saving the decision for %s", reference_no)
        raise HTTPException(
            status_code=500, detail="Unexpected error while saving the decision"
        )

    return result


def _nod_out(nod) -> dict:
    """One NOD as the API returns it."""
    return {
        "nod_number": nod.nod_number,
        "activity": nod.activity,
        "deficiencies": nod.deficiencies,
        "requested_documents": nod.requested_documents or [],
        "issued_date": nod.issued_date,
        "working_days": nod.working_days,
        "due_date": nod.due_date,
        "extended_due_date": nod.extended_due_date,
        "extension_reason": nod.extension_reason,
        "extended_at": nod.extended_at,
        "documents_received_date": nod.documents_received_date,
        "status": nod.status,
        "issued_by": (
            f"{nod.issued_by.first_name or ''} {nod.issued_by.surname or ''}".strip()
            if nod.issued_by
            else None
        ),
        "email_sent_at": nod.email_sent_at,
    }


@router.get("/claimed/{reference_no}/nods", response_model=list[NodOut])
def get_nods(
    reference_no: str,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The Notices of Deficiency issued on an application. Same access rule as
    the application itself: only people who have worked on it."""
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
    return [_nod_out(n) for n in list_nods(internal_db, application.application_uuid)]


def _load_nod_for_evaluator(
    internal_db: Session, reference_no: str, nod_number: int, user
):
    """Extending or recording documents is the evaluator's job: the caller must
    hold the task at the Quality Evaluation step. The NOD row is locked."""
    application, task = _require_step_holder(internal_db, reference_no, user)
    if task.application_step != EVALUATOR_STEP:
        raise HTTPException(
            status_code=403,
            detail=f"Only the {EVALUATOR_STEP} step can change a Notice of Deficiency",
        )
    nod = (
        internal_db.query(EAppNoticeOfDeficiency)
        .filter(
            EAppNoticeOfDeficiency.application_uuid == application.application_uuid,
            EAppNoticeOfDeficiency.nod_number == nod_number,
            EAppNoticeOfDeficiency.is_deleted.is_(False),
        )
        .with_for_update()
        .first()
    )
    if not nod:
        raise HTTPException(status_code=404, detail="Notice of Deficiency not found")
    return nod


@router.post("/claimed/{reference_no}/nods/{nod_number}/extend", response_model=NodOut)
def post_nod_extension(
    reference_no: str,
    nod_number: int,
    payload: NodExtendRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    nod = _load_nod_for_evaluator(internal_db, reference_no, nod_number, current_user)
    try:
        extend_nod(nod, current_user.user_uuid, payload.new_due_date, payload.reason)
        internal_db.commit()
    except ValueError as err:
        internal_db.rollback()
        raise HTTPException(status_code=422, detail=str(err))
    internal_db.refresh(nod)
    return _nod_out(nod)


@router.post("/claimed/{reference_no}/nods/{nod_number}/receive", response_model=NodOut)
def post_nod_documents_received(
    reference_no: str,
    nod_number: int,
    payload: NodReceiveRequest,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    nod = _load_nod_for_evaluator(internal_db, reference_no, nod_number, current_user)
    try:
        receive_documents(
            nod, current_user.user_uuid, payload.received_ids, payload.received_date
        )
        internal_db.commit()
    except ValueError as err:
        internal_db.rollback()
        raise HTTPException(status_code=422, detail=str(err))
    internal_db.refresh(nod)
    return _nod_out(nod)


def _worksheet_response(internal_db: Session, application, can_edit: bool) -> dict:
    # The evaluator sees their latest version, even a draft. Everyone else sees
    # the latest version that was sent on.
    row = latest_worksheet(
        internal_db, application.application_uuid, submitted_only=not can_edit
    )
    return {
        "worksheet": build_worksheet_out(internal_db, row) if row else None,
        "can_edit": can_edit,
    }


@router.get("/claimed/{reference_no}/worksheet", response_model=WorksheetResponse)
def get_worksheet(
    reference_no: str,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """The GMP Clearance Worksheet. Same access rule as the application itself:
    only people who have worked on it."""
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
    task = open_task_held_by(
        internal_db, application.application_uuid, current_user.user_uuid
    )
    can_edit = bool(task and task.application_step == EVALUATOR_STEP)
    return _worksheet_response(internal_db, application, can_edit)


@router.put("/claimed/{reference_no}/worksheet", response_model=WorksheetResponse)
def put_worksheet(
    reference_no: str,
    payload: WorksheetIn,
    internal_db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """Auto-save while the evaluator types. Only the evaluator holding the
    Quality Evaluation task may save."""
    application, task = _require_step_holder(internal_db, reference_no, current_user)
    if task.application_step != EVALUATOR_STEP:
        raise HTTPException(
            status_code=403,
            detail=f"Only the {EVALUATOR_STEP} step can change the worksheet",
        )
    try:
        save_worksheet_draft(
            internal_db, application, current_user.user_uuid, payload.model_dump()
        )
        internal_db.commit()
    except ValueError as err:
        internal_db.rollback()
        raise HTTPException(status_code=422, detail=str(err))
    except Exception:
        internal_db.rollback()
        logger.exception("Unexpected error saving the worksheet for %s", reference_no)
        raise HTTPException(
            status_code=500, detail="Unexpected error while saving the worksheet"
        )
    return _worksheet_response(internal_db, application, True)


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
            _evaluators_query(internal_db, current_user)
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
