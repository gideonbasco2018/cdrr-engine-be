# app/services/fgmp_nod.py
"""Notice of Deficiency (NOD): what the "For Compliance" action creates.

The rules live here, in one place, and mirror the browser copy the screen
uses for its previews (fgmpNod.js in the frontend) -- change both together.

Nothing here commits. The caller commits or rolls back, so issuing a NOD is
part of the same transaction as the decision that created it.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.e_app_history import EAppHistory
from app.models.e_app_notice_of_deficiency import (
    NOD_STATUS_COMPLIED,
    NOD_STATUS_WAITING,
    EAppNoticeOfDeficiency,
)
from app.models.e_application import EApplication

MAX_NODS = 5
NOD_WORKING_DAYS = 5

PH_TZ = timezone(timedelta(hours=8))  # the Philippines has no DST


def today_ph() -> date:
    return datetime.now(PH_TZ).date()


def add_working_days(start: date, days: int) -> date:
    """`days` working days after `start`. Saturdays and Sundays do not count.
    Holidays are not skipped: the system has no holiday list yet."""
    current = start
    left = days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0 .. Friday=4
            left -= 1
    return current


def effective_due_date(nod: EAppNoticeOfDeficiency) -> date:
    """The date that counts: the latest extension, else the original."""
    return nod.extended_due_date or nod.due_date


def list_nods(db: Session, application_uuid: str) -> list[EAppNoticeOfDeficiency]:
    return (
        db.query(EAppNoticeOfDeficiency)
        .filter(
            EAppNoticeOfDeficiency.application_uuid == application_uuid,
            EAppNoticeOfDeficiency.is_deleted.is_(False),
        )
        .order_by(EAppNoticeOfDeficiency.nod_number)
        .all()
    )


def _document_entries(names: list[str] | None) -> list[dict]:
    """The documents asked for, one entry each. Blank lines are dropped."""
    entries = []
    for name in names or []:
        text = (name or "").strip()
        if text:
            entries.append(
                {
                    "id": uuid.uuid4().hex[:12],
                    "requirement_code": text,
                    "status": "REQUESTED",
                    "document_id": None,  # e_app_documents.id once uploaded
                    "filename": None,
                }
            )
    return entries


def issue_nod(
    db: Session,
    application: EApplication,
    history: EAppHistory,
    user_uuid: str,
    deficiencies: str | None,
    documents: list[str] | None,
    issued_date: date | None = None,
) -> EAppNoticeOfDeficiency:
    """Create the next NOD for the application. Raises ValueError if it cannot."""
    text = (deficiencies or "").strip()
    if not text:
        raise ValueError("Write what is lacking")

    # Count every row, soft-deleted ones included: the unique rule on
    # (application, nod_number) does too.
    highest = (
        db.query(func.max(EAppNoticeOfDeficiency.nod_number))
        .filter(EAppNoticeOfDeficiency.application_uuid == application.application_uuid)
        .scalar()
        or 0
    )
    number = highest + 1
    if number > MAX_NODS:
        raise ValueError(f"Maximum of {MAX_NODS} NODs reached")

    issued = issued_date or today_ph()
    nod = EAppNoticeOfDeficiency(
        application_uuid=application.application_uuid,
        history_uuid=history.history_uuid,
        activity=application.activity or "",
        nod_number=number,
        deficiencies=text,
        requested_documents=_document_entries(documents),
        issued_date=issued,
        working_days=NOD_WORKING_DAYS,
        due_date=add_working_days(issued, NOD_WORKING_DAYS),
        status=NOD_STATUS_WAITING,
        issued_by_user_uuid=user_uuid,
        is_deleted=False,
    )
    db.add(nod)
    db.flush()
    return nod


def extend_nod(
    nod: EAppNoticeOfDeficiency,
    user_uuid: str,
    new_due_date: date,
    reason: str | None,
) -> EAppNoticeOfDeficiency:
    """Move the deadline forward. May be done again, and may be done after the
    deadline has passed (the applicant can still be given more time)."""
    if nod.status == NOD_STATUS_COMPLIED:
        raise ValueError("This NOD is already complied")
    if new_due_date <= effective_due_date(nod):
        raise ValueError("The new due date must be later than the current one")
    text = (reason or "").strip()
    if not text:
        raise ValueError("Write the reason for the extension")
    nod.extended_due_date = new_due_date
    nod.extension_reason = text
    nod.extended_by_user_uuid = user_uuid
    nod.extended_at = datetime.now(PH_TZ).replace(tzinfo=None)
    return nod


def receive_documents(
    nod: EAppNoticeOfDeficiency,
    user_uuid: str,
    received_ids: list[str],
    received_date: date | None,
) -> EAppNoticeOfDeficiency:
    """Mark documents as received. Once every requested one is in, the NOD is
    complied and the date is kept. With nothing requested, the date alone
    complies it."""
    if nod.status == NOD_STATUS_COMPLIED:
        raise ValueError("This NOD is already complied")
    received_on = received_date or today_ph()

    ticked = set(received_ids or [])
    documents = [dict(d) for d in (nod.requested_documents or [])]
    unknown = ticked - {d.get("id") for d in documents}
    if unknown:
        raise ValueError("Unknown document selected")
    for doc in documents:
        if doc.get("id") in ticked:
            doc["status"] = "RECEIVED"
    # assign a new list so the JSON column is seen as changed
    nod.requested_documents = documents

    if all(d.get("status") == "RECEIVED" for d in documents):
        nod.status = NOD_STATUS_COMPLIED
        nod.documents_received_date = received_on
        nod.received_by_user_uuid = user_uuid
    return nod
