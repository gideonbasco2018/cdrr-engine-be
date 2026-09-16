# app/crud/donation.py

import re
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional, List

from app.models.donation import Donation, DonationChangeLog
from app.schemas.donation import DonationCreate, DonationUpdate

# Letter DTN is a 14-digit code (e.g. a YYYYMMDDHHMMSS-style timestamp id)
# — shared by the Pydantic schemas (manual create/update) and here (Excel
# import), so both paths reject the same malformed values the same way.
LETTER_DTN_RE = re.compile(r"^\d{14}$")

# Display label per column — mirrors INFO_FIELDS in DonationPage.jsx so
# change-log entries read the same on both ends.
FIELD_LABELS = {
    "letter_dtn": "Letter DTN",
    "date_received": "Date Received By Center",
    "date_received_by_evaluator": "Date Received by Evaluator",
    "donor": "Donor",
    "donee": "Donee/Recipient",
    "registration_dtn": "Registration DTN",
    "product_name": "Product Name",
    "packaging": "Packaging",
    "manufacturer": "Manufacturer",
    "batch_lot_no": "Batch/Lot No.",
    "expiration_date": "Expiration Date",
    "total_quantity": "Total Quantity",
    "validity": "Validity (Expired on)",
    "date_issued": "Date Issue",
    "evaluator": "Evaluator",
    "status": "Status",
    "donation_reg_no": "Donation Registration No.",
    "date_forwarded_to_checker": "Date Forwarded to Checker",
    "date_released": "Date Released from CDRR",
    "remarks": "Remarks",
}


class StaleVersionError(Exception):
    """Raised by update_donation() when the caller's expected_version no
    longer matches — someone else saved a change in between."""

    def __init__(self, current_version: int):
        self.current_version = current_version
        super().__init__(f"Record has moved on to version {current_version}")


class DuplicateLetterDtnError(Exception):
    """Raised by create_donation() when the Letter DTN is already used by
    another record — mirrors the duplicate check bulk_create_donations
    already runs for Excel imports, so a manually-created row can't slip
    past the same rule."""

    def __init__(self, letter_dtn: str, existing_id: int):
        self.letter_dtn = letter_dtn
        self.existing_id = existing_id
        super().__init__(f"Letter DTN {letter_dtn!r} already exists (record #{existing_id})")


def get_all_donations(
    db: Session, skip: int = 0, limit: Optional[int] = None
) -> List[Donation]:
    """`limit=None` returns everything (today's behavior — this table is
    small). Pass skip/limit to page through it once it grows."""
    query = (
        db.query(Donation)
        .filter(Donation.is_deleted == 0)
        .order_by(Donation.id.desc())
        .offset(skip)
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def count_donations(db: Session) -> int:
    return db.query(Donation).filter(Donation.is_deleted == 0).count()


def get_deleted_donations(db: Session) -> List[Donation]:
    return (
        db.query(Donation)
        .filter(Donation.is_deleted == 1)
        .order_by(Donation.deleted_at.desc())
        .all()
    )


def get_donation_by_id(db: Session, donation_id: int) -> Optional[Donation]:
    return (
        db.query(Donation)
        .filter(Donation.id == donation_id, Donation.is_deleted == 0)
        .first()
    )


def get_donation_by_id_any(db: Session, donation_id: int) -> Optional[Donation]:
    """Same lookup, but doesn't hide soft-deleted rows — used where a
    deleted record still needs to be reachable (its change log, restore)."""
    return db.query(Donation).filter(Donation.id == donation_id).first()


def soft_delete_donation(db: Session, donation_id: int, username: str) -> Optional[Donation]:
    """Mark a donation record as deleted without removing the row — it
    (and its change log) stays in the database, just hidden from the
    normal list/get/update endpoints."""
    donation = get_donation_by_id(db, donation_id)
    if not donation:
        return None
    donation.is_deleted = 1
    donation.deleted_at = datetime.now(timezone.utc)
    donation.deleted_by = username
    db.commit()
    db.refresh(donation)
    return donation


def restore_donation(db: Session, donation_id: int, username: str) -> Optional[Donation]:
    """Undo a soft delete."""
    donation = db.query(Donation).filter(
        Donation.id == donation_id, Donation.is_deleted == 1
    ).first()
    if not donation:
        return None
    donation.is_deleted = 0
    donation.deleted_at = None
    donation.deleted_by = None
    donation.updated_by = username
    db.commit()
    db.refresh(donation)
    return donation


def create_donation(db: Session, payload: DonationCreate, username: str) -> Donation:
    data = payload.model_dump()
    data["status"] = data.get("status") or "For Evaluation"

    existing = (
        db.query(Donation).filter(Donation.letter_dtn == data["letter_dtn"]).first()
    )
    if existing:
        raise DuplicateLetterDtnError(data["letter_dtn"], existing.id)

    donation = Donation(
        **data,
        created_by=username,
        updated_by=username,
        upload_by=username,
    )
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation


def update_donation(
    db: Session,
    donation_id: int,
    payload: DonationUpdate,
    username: str,
    expected_version: Optional[int] = None,
) -> Optional[Donation]:
    donation = get_donation_by_id(db, donation_id)
    if not donation:
        return None
    if expected_version is not None and expected_version != donation.version:
        raise StaleVersionError(donation.version)

    changes = payload.model_dump(exclude_unset=True)
    changes.pop("version", None)  # concurrency token, not a real field
    changed_any = False
    for field, new_value in changes.items():
        old_value = getattr(donation, field)
        if (old_value or None) == (new_value or None):
            continue
        db.add(
            DonationChangeLog(
                donation_id=donation.id,
                field=FIELD_LABELS.get(field, field),
                old_value=old_value,
                new_value=new_value,
                changed_by=username,
            )
        )
        setattr(donation, field, new_value)
        changed_any = True

    if changed_any:
        donation.version += 1
        donation.updated_by = username
    db.commit()
    db.refresh(donation)
    return donation


def get_change_log(db: Session, donation_id: int) -> List[DonationChangeLog]:
    return (
        db.query(DonationChangeLog)
        .filter(DonationChangeLog.donation_id == donation_id)
        .order_by(DonationChangeLog.changed_at.desc())
        .all()
    )


def bulk_create_donations(
    db: Session, rows: List[dict], username: str
) -> tuple[int, int, int, int, list[str]]:
    """Insert many donations at once (Excel import). Skips fully-blank
    rows, rows with no Letter DTN or one that isn't a 14-digit number (a
    DTN is required to insert a row — it's how duplicates are detected
    and how the record is identified everywhere else), and rows whose
    Letter DTN already exists (already-imported or duplicated within the
    same file). Returns (created_count, skipped_duplicate_count,
    skipped_no_dtn_count, skipped_invalid_dtn_count, error_messages) —
    one failed row doesn't abort the rest, each is attempted
    independently."""
    existing_dtns = {
        dtn
        for (dtn,) in db.query(Donation.letter_dtn).filter(Donation.letter_dtn.isnot(None)).all()
    }
    seen_in_file = set()

    created = 0
    skipped_duplicates = 0
    skipped_no_dtn = 0
    skipped_invalid_dtn = 0
    errors: list[str] = []
    for idx, row in enumerate(rows, start=2):  # row 1 is the header
        if not any((v or "").strip() for v in row.values()):
            continue

        dtn = (row.get("letter_dtn") or "").strip()
        if not dtn:
            skipped_no_dtn += 1
            continue
        if not LETTER_DTN_RE.match(dtn):
            skipped_invalid_dtn += 1
            continue
        if dtn in existing_dtns or dtn in seen_in_file:
            skipped_duplicates += 1
            continue

        row = dict(row)
        row["letter_dtn"] = dtn
        row["status"] = row.get("status") or "For Evaluation"
        try:
            donation = Donation(
                **row, created_by=username, updated_by=username, upload_by=username
            )
            db.add(donation)
            db.commit()
            created += 1
            seen_in_file.add(dtn)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            errors.append(f"Row {idx}: {exc}")
    return created, skipped_duplicates, skipped_no_dtn, skipped_invalid_dtn, errors
