# app/services/fgmp_worksheet.py
"""The FGMP evaluator's GMP Clearance Worksheet, saved by version.

While the evaluator works, the latest row is a DRAFT that is updated in
place. When the application is forwarded the draft is locked (SUBMITTED).
If it comes back and the evaluator changes the worksheet, a new version is
started as a copy, so the earlier version stays exactly as the Checker saw it.
Saving the same content again never makes a new version.

Nothing here commits. The caller commits or rolls back, so locking a
worksheet is part of the same transaction as the decision that forwards it.
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.e_app_fgmp_worksheet import (
    WORKSHEET_STATUS_DRAFT,
    WORKSHEET_STATUS_SUBMITTED,
    EAppFgmpWorksheet,
)
from app.models.e_app_history import EAppHistory
from app.models.e_application import EApplication
from app.models.user import User

PH_TZ = timezone(timedelta(hours=8))  # the Philippines has no DST

CHECKER_STEP = "Checker"

RECOMMENDATIONS = ("APPROVED", "FOR INSPECTION", "FOR COMPLIANCE", "DENIAL")

# The fields the evaluator fills in, and so the only ones a save may set
TEXT_FIELDS = (
    "issuing_authority",
    "issuing_country",
    "foreign_certificate_number",
    "foreign_certificate_validity",
    "inspection_dates",
    "date_issued_text",
    "approved_dosage_forms_note",
    "remarks",
    "compliance_notes",
    "recommendation",
)
JSON_FIELDS = (
    "gmp_evidence",
    "applied_forms",
    "approved_products",
    "annex_c",
    "annex_rows",
)
FIELDS = TEXT_FIELDS + JSON_FIELDS


def now_ph() -> datetime:
    return datetime.now(PH_TZ).replace(tzinfo=None)


def variant_for(application: EApplication) -> str:
    """A for a PIC/S member, B for everything else (Non-PIC/S)."""
    category = (application.fgmp.category if application.fgmp else "") or ""
    return "A" if category.strip().upper() == "PIC/S" else "B"


# ───────── cleaning what the screen sends ─────────


def _text(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _lines(values) -> list[str]:
    return [t for t in (_text(v) for v in (values or [])) if t]


def _forms(rows) -> list[dict]:
    """Annex B / Approved Medicinal Products rows. Empty rows are dropped."""
    cleaned = []
    for row in rows or []:
        entry = {
            "dosage_forms": _lines(row.get("dosage_forms")),
            "product_type": _text(row.get("product_type")),
            "operations": _lines(row.get("operations")),
        }
        if entry["dosage_forms"] or entry["product_type"] or entry["operations"]:
            cleaned.append(entry)
    return cleaned


def normalize(values: dict) -> dict:
    """The worksheet as it is stored: text trimmed, empty things empty."""
    values = values or {}
    recommendation = _text(values.get("recommendation"))
    if recommendation and recommendation not in RECOMMENDATIONS:
        raise ValueError("Unknown recommendation")
    annex_c = {
        key: text
        for key, text in ((k, _text(v)) for k, v in (values.get("annex_c") or {}).items())
        if text
    }
    annex_rows = [
        {
            "id": str(r.get("id") or ""),
            "after": int(r.get("after") or 0),
            "contents": _text(r.get("contents")) or "",
            "remarks": _text(r.get("remarks")) or "",
        }
        for r in (values.get("annex_rows") or [])
        if _text(r.get("contents")) or _text(r.get("remarks"))
    ]
    out = {name: _text(values.get(name)) for name in TEXT_FIELDS}
    out["recommendation"] = recommendation
    out["gmp_evidence"] = _lines(values.get("gmp_evidence"))
    out["applied_forms"] = _forms(values.get("applied_forms"))
    out["approved_products"] = _forms(values.get("approved_products"))
    out["annex_c"] = annex_c
    out["annex_rows"] = annex_rows
    return out


def _stored(row: EAppFgmpWorksheet) -> dict:
    """The row's worksheet values in the same shape normalize() returns, so two
    worksheets can be compared."""
    return normalize({name: getattr(row, name) for name in FIELDS})


# ───────── versions ─────────


def latest_row(
    db: Session,
    application_uuid: str,
    submitted_only: bool = False,
    lock: bool = False,
) -> EAppFgmpWorksheet | None:
    query = db.query(EAppFgmpWorksheet).filter(
        EAppFgmpWorksheet.application_uuid == application_uuid,
        EAppFgmpWorksheet.is_deleted.is_(False),
    )
    if submitted_only:
        query = query.filter(EAppFgmpWorksheet.status == WORKSHEET_STATUS_SUBMITTED)
    query = query.order_by(EAppFgmpWorksheet.version.desc())
    if lock:
        query = query.with_for_update()
    return query.first()


def _fill(row: EAppFgmpWorksheet, values: dict, user_uuid: str, variant: str) -> None:
    for name in FIELDS:
        setattr(row, name, values[name])
    row.variant = variant
    row.saved_by_user_uuid = user_uuid
    row.saved_at = now_ph()


def save_draft(
    db: Session, application: EApplication, user_uuid: str, values: dict
) -> EAppFgmpWorksheet:
    """Save what the evaluator has typed so far.

    - nothing saved yet: version 1, a draft
    - the latest is a draft: it is updated in place
    - the latest is locked: identical content changes nothing; different
      content starts the next version, as a draft
    """
    cleaned = normalize(values)
    variant = variant_for(application)
    latest = latest_row(db, application.application_uuid, lock=True)

    if latest is None:
        row = EAppFgmpWorksheet(
            application_uuid=application.application_uuid,
            version=1,
            status=WORKSHEET_STATUS_DRAFT,
            variant=variant,
            saved_by_user_uuid=user_uuid,
            is_deleted=False,
        )
        _fill(row, cleaned, user_uuid, variant)
        db.add(row)
        db.flush()
        return row

    if latest.status == WORKSHEET_STATUS_DRAFT:
        _fill(latest, cleaned, user_uuid, variant)
        db.flush()
        return latest

    if _stored(latest) == cleaned:
        return latest

    row = EAppFgmpWorksheet(
        application_uuid=application.application_uuid,
        version=latest.version + 1,
        status=WORKSHEET_STATUS_DRAFT,
        variant=variant,
        saved_by_user_uuid=user_uuid,
        is_deleted=False,
    )
    _fill(row, cleaned, user_uuid, variant)
    db.add(row)
    db.flush()
    return row


def lock_for_forwarding(
    db: Session,
    application: EApplication,
    user_uuid: str,
    history: EAppHistory,
    values: dict | None = None,
) -> EAppFgmpWorksheet | None:
    """The application is being sent on: save the final worksheet (when the
    screen sends it) and lock the draft. Nothing to lock when the evaluator
    never filled anything in, or when the worksheet was already sent and
    nothing changed since."""
    if values is not None:
        row = save_draft(db, application, user_uuid, values)
    else:
        row = latest_row(db, application.application_uuid, lock=True)
    if row is None:
        return None
    if row.status == WORKSHEET_STATUS_DRAFT:
        row.status = WORKSHEET_STATUS_SUBMITTED
        row.history_uuid = history.history_uuid
        row.saved_by_user_uuid = user_uuid
        row.saved_at = now_ph()
        db.flush()
    return row


# ───────── what the Checker and the later steps read ─────────


def _person(db: Session, user_uuid: str | None) -> dict:
    user = db.query(User).filter(User.user_uuid == user_uuid).first() if user_uuid else None
    if not user:
        return {"name": None, "designation": None}
    name = f"{user.first_name or ''} {user.surname or ''}".strip()
    return {"name": name or None, "designation": _text(user.position)}


def evaluated_dates(
    db: Session, application_uuid: str, up_to_version: int
) -> list[date]:
    """The day each earlier round was sent on, oldest first."""
    rows = (
        db.query(EAppFgmpWorksheet.saved_at)
        .filter(
            EAppFgmpWorksheet.application_uuid == application_uuid,
            EAppFgmpWorksheet.is_deleted.is_(False),
            EAppFgmpWorksheet.status == WORKSHEET_STATUS_SUBMITTED,
            EAppFgmpWorksheet.version <= up_to_version,
        )
        .order_by(EAppFgmpWorksheet.version)
        .all()
    )
    return [r[0].date() for r in rows if r[0]]


def checker_info(db: Session, application_uuid: str) -> dict | None:
    """Who checked it and when: the latest Checker task. The date is empty
    until they send their decision."""
    task = (
        db.query(EAppHistory)
        .filter(
            EAppHistory.application_uuid == application_uuid,
            EAppHistory.application_step == CHECKER_STEP,
        )
        .order_by(EAppHistory.del_index.desc())
        .first()
    )
    if not task or not task.user_uuid:
        return None
    person = _person(db, task.user_uuid)
    person["date"] = task.accomplished_date.date() if task.accomplished_date else None
    return person


def build_out(db: Session, row: EAppFgmpWorksheet) -> dict:
    """One version as the API returns it, with the parts that fill themselves."""
    out = {name: getattr(row, name) for name in FIELDS}
    out["gmp_evidence"] = row.gmp_evidence or []
    out["applied_forms"] = row.applied_forms or []
    out["approved_products"] = row.approved_products or []
    out["annex_c"] = row.annex_c or {}
    out["annex_rows"] = row.annex_rows or []
    out.update(
        version=row.version,
        status=row.status,
        variant=row.variant,
        saved_at=row.saved_at,
        evaluated_by={
            **_person(db, row.saved_by_user_uuid),
            "dates": evaluated_dates(db, row.application_uuid, row.version),
        },
        checked_by=checker_info(db, row.application_uuid),
    )
    return out
