# app/services/fgmp_workflow.py
"""The FGMP e-application workflow, from the Evaluator step onwards.

    Decker -> Evaluator -> Checker -> Supervisor -> LRD Chief -> Director

This is the new system's own flow. It is NOT the manual FGMP flow in
app/crud/gmp_record.py, which has no Supervisor step and goes through QA
Admin, OD Receiving and OD Releasing instead.

The Decker step is handled elsewhere (app/services/decking_decision.py).
"Disapprove" actions are not built yet.
"""
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.e_app_history import EAppHistory
from app.models.e_application import EApplication
from app.services.appointment_claim import DEL_LAST_INDEX, DEL_THREAD_OPEN
from app.services.appointment_payment import (
    CLOSED_LAST_INDEX,
    CLOSED_THREAD,
    COMPLETED_STATUS,
)

NEXT_STATUS = "IN PROGRESS"

# Step labels, also used as the tab titles on the e-application page
DECKER_STEP = "Decking"
EVALUATOR_STEP = "Quality Evaluation"
CHECKER_STEP = "Checker"
SUPERVISOR_STEP = "Supervisor"
LRD_CHIEF_STEP = "LRD Chief"
DIRECTOR_STEP = "Director"

# Step -> the user group that handles it. The last two steps have no
# FGMP-specific group, so they use the shared ones.
STEP_GROUP_IDS: dict[str, int] = {
    EVALUATOR_STEP: 31,    # FGMP Evaluator
    CHECKER_STEP: 32,      # FGMP Checker
    SUPERVISOR_STEP: 33,   # FGMP Supervisor
    LRD_CHIEF_STEP: 17,    # LRD Chief Admin (shared)
    DIRECTOR_STEP: 7,      # Director (shared)
}

# (current step, action) -> the step that follows, or None when the action
# ends the workflow. This table is the only place routing is defined: the
# screen asks for the actions of its step, and a decision not listed here is
# rejected, so the dropdown can never offer something invalid.
#
# To add a step, add its rows here and its group above. Nothing else changes.
ACTION_ROUTES: dict[tuple[str, str], str | None] = {
    (EVALUATOR_STEP, "Endorse to Checker"): CHECKER_STEP,
    (EVALUATOR_STEP, "Endorse to Supervisor"): SUPERVISOR_STEP,
    # "For Compliance" loops back to the same step and the same evaluator: the
    # current task closes as COMPLETED (so the round trip shows up in the
    # application's history) and a fresh one opens for them.
    (EVALUATOR_STEP, "For Compliance"): EVALUATOR_STEP,

    (CHECKER_STEP, "Endorse to Supervisor"): SUPERVISOR_STEP,
    (CHECKER_STEP, "Return to Evaluator"): EVALUATOR_STEP,

    (SUPERVISOR_STEP, "Endorse to LRD Chief"): LRD_CHIEF_STEP,
    (SUPERVISOR_STEP, "Return to Evaluator"): EVALUATOR_STEP,

    (LRD_CHIEF_STEP, "Endorse to Director"): DIRECTOR_STEP,
    (LRD_CHIEF_STEP, "Return to Supervisor"): SUPERVISOR_STEP,

    # "Approved" ends the workflow: the task closes and no new one opens.
    (DIRECTOR_STEP, "Approved"): None,
    (DIRECTOR_STEP, "Return to LRD Chief"): LRD_CHIEF_STEP,
}

# The action a step offers is present tense ("Endorse to Checker") — it's a
# choice being made. What gets written to application_decision (and read back
# later, e.g. the Processed tab's history) is past tense ("Endorsed to
# Checker") — it's a record of what already happened. Only entries that
# change meaning need listing; anything missing is stored as submitted
# ("For Compliance", "Approved" already read fine either way).
PAST_TENSE_DECISION = {
    "Endorse to Checker": "Endorsed to Checker",
    "Endorse to Supervisor": "Endorsed to Supervisor",
    "Endorse to LRD Chief": "Endorsed to LRD Chief",
    "Endorse to Director": "Endorsed to Director",
    "Return to Evaluator": "Returned to Evaluator",
    "Return to Supervisor": "Returned to Supervisor",
    "Return to LRD Chief": "Returned to LRD Chief",
}

# Steps this service handles (Decking is not one of them)
WORKFLOW_STEPS = set(STEP_GROUP_IDS)

# What may be issued for an FGMP application. Same list the manual FGMP
# screen offers (GMP_TYPE_OF_ISSUANCE_APPROVED_OPTIONS +
# GMP_DISAPPROVED_TYPE_OF_ISSUANCE in
# cdrr-engine-fe/src/components/gmp/shared/constants.js). The e-application
# screen reads it from here so the two lists cannot drift apart.
TYPE_OF_ISSUANCE_OPTIONS = [
    "CGMP Clearance",
    # The two cGMP Clearance templates are the same certificate except for one
    # phrase — "after desktop evaluation of the submitted GMP documentary
    # evidence" or "after on-site inspection". Picking one of these says which
    # wording to print, so nothing else has to record it.
    "Certificate of GMP Compliance - Desktop evaluation",
    "Certificate of GMP Compliance - On-site inspection",
    "CGMP Clearance - COC",
    "Notice for Inspection - Fresh Application",
    "Notice for Inspection - Renewal Application",
    "NFI due to Non-compliance",
    "Extension of Validity",
    "Permit to Register",
    "Acknowledgement Letter",
    # The unit has three disapproval letters, each citing a different rule, so
    # the reason is chosen here rather than left vague.
    "Letter of Disapproval - Incomplete Requirements",
    "Letter of Disapproval - Foreign Inspection",
    "Letter of Disapproval - Non-compliance to NOD",
]

# The step whose holder decides what will be issued
TYPE_OF_ISSUANCE_STEP = EVALUATOR_STEP

# Only these produce a certificate with a number of its own. Everything else
# is a letter or a notice, or is numbered another way:
#   - a COC uses CDRR-CGMP-FA-{foreign manufacturer no}-{sequence}
#     (e.g. CDRR-CGMP-FA-289-02), and nothing here holds that manufacturer
#     number, so it is left for someone to fill in
#   - an extension quotes the certificate it extends, it does not make a new one
CERTIFICATE_ISSUANCE_TYPES = {
    "CGMP Clearance",
    "Certificate of GMP Compliance - Desktop evaluation",
    "Certificate of GMP Compliance - On-site inspection",
}

# Matches the numbering already in use on the manual GMP records, e.g.
# "CDRR-CGMP-5921". Those records also hold a second, older format
# ("CDRR-CGMP-FA-291-02"), which is left alone.
CERTIFICATE_NUMBER_PREFIX = "CDRR-CGMP-"


def next_certificate_number(db: Session) -> str:
    """The next number in the CDRR-CGMP-#### series.

    Counts the manual GMP records as well as the e-applications, so the two
    systems cannot hand out the same number.
    """
    highest = 0
    statement = text(
        "SELECT MAX(CAST(SUBSTRING(n, :cut) AS UNSIGNED)) FROM ("
        "  SELECT certificate_number AS n FROM e_application_fgmp"
        "   WHERE certificate_number REGEXP :pattern"
        "  UNION ALL"
        "  SELECT GMP_CERTIFICATE_NUMBER AS n FROM gmp_record"
        "   WHERE GMP_CERTIFICATE_NUMBER REGEXP :pattern"
        ") AS numbered"
    )
    found = db.execute(
        statement,
        {
            "cut": len(CERTIFICATE_NUMBER_PREFIX) + 1,
            "pattern": f"^{CERTIFICATE_NUMBER_PREFIX}[0-9]+$",
        },
    ).scalar()
    if found:
        highest = int(found)
    return f"{CERTIFICATE_NUMBER_PREFIX}{highest + 1}"

# A step that routes to itself keeps the task with the same person, so nobody
# is picked (currently only "For Compliance").
SELF_LOOP_ROUTES = {
    key for key, nxt in ACTION_ROUTES.items() if nxt == key[0]
}


def actions_for_step(step: str) -> list[dict]:
    """Every action valid at `step`, with where each one leads.

    The screen builds its dropdown from this, so it can never offer an action
    that submit_step_decision would reject.
    """
    return [
        {"action": action, "next_step": next_step}
        for (s, action), next_step in ACTION_ROUTES.items()
        if s == step
    ]


def resolve_next_step(current_step: str, action: str) -> tuple[bool, str | None]:
    """Returns (is_valid_route, next_step_label)."""
    route_key = (current_step, action)
    if route_key not in ACTION_ROUTES:
        return False, None
    return True, ACTION_ROUTES[route_key]


def open_task_held_by(db: Session, application_uuid: str, user_uuid: str):
    """The user's own open task on this application, or None."""
    return (
        db.query(EAppHistory)
        .filter(
            EAppHistory.application_uuid == application_uuid,
            EAppHistory.user_uuid == user_uuid,
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
        .first()
    )


def submit_step_decision(
    db: Session,
    application: EApplication,
    user_uuid: str,
    decision: str,
    remarks: str | None,
    assignee_uuid: str | None,
    type_of_issuance: str | None = None,
) -> dict:
    """Close the user's open task and, unless the action ends the workflow,
    open the next step's task.

    Does NOT commit. The caller commits or rolls back.
    Raises PermissionError when the task is not held by the user, and
    ValueError for an unknown action or a missing assignee.
    """
    remarks = (remarks or "").strip() or None

    history = (
        db.query(EAppHistory)
        .filter(
            EAppHistory.application_uuid == application.application_uuid,
            EAppHistory.user_uuid == user_uuid,
            EAppHistory.del_thread == DEL_THREAD_OPEN,
            EAppHistory.del_last_index == DEL_LAST_INDEX,
        )
        .with_for_update()
        .first()
    )
    if not history:
        raise PermissionError("This task is not currently assigned to you")

    current_step = history.application_step
    if current_step not in WORKFLOW_STEPS:
        raise ValueError(f"The '{current_step}' step is not handled here")

    is_valid_route, next_step = resolve_next_step(current_step, decision)
    if not is_valid_route:
        raise ValueError(f"'{decision}' is not allowed at the {current_step} step")

    # What will be issued — optional, and only the step that decides it may set it
    type_of_issuance = (type_of_issuance or "").strip() or None
    if type_of_issuance:
        if current_step != TYPE_OF_ISSUANCE_STEP:
            raise ValueError(
                f"The type of issuance is set at the {TYPE_OF_ISSUANCE_STEP} step"
            )
        if type_of_issuance not in TYPE_OF_ISSUANCE_OPTIONS:
            raise ValueError(f"Unknown type of issuance: {type_of_issuance}")
        if application.fgmp is None:
            raise ValueError("This application has no FGMP details to write to")
        application.fgmp.type_of_issuance = type_of_issuance

        # A certificate needs a number; give it one the first time, and keep
        # it if the evaluator later changes their mind about the type.
        needs_certificate = type_of_issuance in CERTIFICATE_ISSUANCE_TYPES
        if needs_certificate and not application.fgmp.certificate_number:
            application.fgmp.certificate_number = next_certificate_number(db)

    # A self-loop stays with the same person; a step that ends the workflow
    # needs nobody; everything else needs someone picked.
    if (current_step, decision) in SELF_LOOP_ROUTES:
        assignee_uuid = user_uuid
    elif next_step is None:
        assignee_uuid = None
    elif not assignee_uuid:
        raise ValueError(f"Select who will handle the {next_step} step")

    # Stored (and later read back as history) in past tense; `decision` itself
    # stays present tense for routing and the API response below.
    history.application_decision = PAST_TENSE_DECISION.get(decision, decision)
    history.application_remarks = remarks
    history.accomplished_date = func.now()
    history.application_status = COMPLETED_STATUS
    history.del_thread = CLOSED_THREAD
    history.del_last_index = CLOSED_LAST_INDEX

    if next_step:
        db.add(
            EAppHistory(
                application_uuid=history.application_uuid,
                process_uuid=history.process_uuid,
                reference_number=history.reference_number,
                user_uuid=assignee_uuid,
                application_step=next_step,
                application_status=NEXT_STATUS,
                start_date=func.now(),
                del_index=(history.del_index or 0) + 1,
                del_previous=history.del_index,
                del_last_index=DEL_LAST_INDEX,
                del_thread=DEL_THREAD_OPEN,
            )
        )

    return {
        "reference_number": application.reference_number,
        "current_step": current_step,
        "decision": decision,
        "next_step": next_step,
        "assignee_uuid": assignee_uuid,
        "type_of_issuance": type_of_issuance,
    }
