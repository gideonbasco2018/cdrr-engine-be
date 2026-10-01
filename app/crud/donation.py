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

# A row with no Letter DTN has nothing to compare against existing records
# with, so "already uploaded" can't be checked by DTN alone — a genuinely
# new row and a re-upload of the same row look identical. As a fallback,
# treat a DTN-less row as a duplicate if EVERY one of these fields matches
# an existing DTN-less row exactly. (letter_dtn itself is excluded — it's
# always blank on both sides of this comparison, so it adds nothing.)
BLANK_DTN_SIGNATURE_FIELDS = [
    "date_received", "date_received_by_evaluator", "donor", "donee",
    "registration_dtn", "product_name", "packaging", "manufacturer",
    "batch_lot_no", "expiration_date", "total_quantity", "validity",
    "date_issued", "evaluator", "status", "donation_reg_no",
    "date_forwarded_to_checker", "date_released", "remarks",
]


def _blank_dtn_signature(data: dict) -> tuple:
    return tuple(data.get(f) for f in BLANK_DTN_SIGNATURE_FIELDS)


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

    # Letter DTN is optional — only check for a duplicate when one was
    # actually given. Without this guard, `Donation.letter_dtn == None`
    # would match on IS NULL and wrongly flag every blank-DTN row after
    # the first as a "duplicate" of it.
    if data.get("letter_dtn"):
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
    db: Session, rows: List[tuple[int, dict]], username: str
) -> tuple[int, int, int, list[str]]:
    """Insert many donations at once (Excel import). `rows` is a list of
    (excel_row_number, row_dict) pairs — not a plain list of dicts —
    because the caller's row reader can skip rows (e.g. a fully-blank
    merged row), so position in the list no longer lines up with "row N
    is the N-th entry"; the real row number travels with each row instead
    so error messages still point at the right place in the spreadsheet.

    Letter DTN is optional
    (a lot of real historical rows never had one) — skips only fully-blank
    rows and rows whose Letter DTN isn't a 14-digit number.

    Duplicate check for a row WITH a Letter DTN is against the DATABASE
    only — a Letter DTN repeating within the same file is NOT treated as a
    duplicate and does not get skipped. This is deliberate: a real
    donation can span several physical Excel rows that legitimately share
    one Letter DTN (a merged DTN cell with a different batch/lot,
    expiration, and quantity per row — see app/api/routes/donation.py's
    merge-fill handling). Skipping "repeats within the file" used to
    silently discard every batch after the first one sharing a DTN — a
    real data-loss bug. Checking only against rows already saved to the
    database still blocks a true re-upload of the same file from creating
    duplicates, since every row's DTN is already there the second time
    around.

    A row with NO Letter DTN has nothing to check that against, so it
    falls back to BLANK_DTN_SIGNATURE_FIELDS — every other field must
    match an existing DTN-less row exactly for it to count as a duplicate.
    That full-row match is checked against both the database AND rows
    already processed earlier in this same file, since (unlike the DTN
    case) there's no legitimate reason for two genuinely different blank-
    DTN rows to match on literally every field — a real multi-batch
    donation always differs in at least its batch/lot or quantity.

    Returns (created_count, skipped_duplicate_count,
    skipped_invalid_dtn_count, error_messages) — one failed row doesn't
    abort the rest, each is attempted independently."""
    existing_dtns = {
        dtn
        for (dtn,) in db.query(Donation.letter_dtn).filter(Donation.letter_dtn.isnot(None)).all()
    }
    existing_blank_dtn_signatures = {
        tuple(sig)
        for sig in db.query(
            *[getattr(Donation, f) for f in BLANK_DTN_SIGNATURE_FIELDS]
        ).filter(Donation.letter_dtn.is_(None)).all()
    }
    seen_blank_dtn_signatures: set[tuple] = set()

    created = 0
    skipped_duplicates = 0
    skipped_invalid_dtn = 0
    errors: list[str] = []
    for idx, row in rows:
        if not any((v or "").strip() for v in row.values()):
            continue

        dtn = (row.get("letter_dtn") or "").strip()
        if dtn and not LETTER_DTN_RE.match(dtn):
            skipped_invalid_dtn += 1
            continue
        if dtn and dtn in existing_dtns:
            skipped_duplicates += 1
            continue

        row = dict(row)
        row["letter_dtn"] = dtn or None
        # Defaulted BEFORE the signature check, not after — the signature
        # must reflect what actually lands in the DB (status included),
        # or a row with no Status never matches its own already-inserted
        # twin (None vs "For Evaluation") and re-inserts every time.
        row["status"] = row.get("status") or "For Evaluation"

        if not dtn:
            signature = _blank_dtn_signature(row)
            if signature in existing_blank_dtn_signatures or signature in seen_blank_dtn_signatures:
                skipped_duplicates += 1
                continue
            seen_blank_dtn_signatures.add(signature)

        try:
            donation = Donation(
                **row, created_by=username, updated_by=username, upload_by=username
            )
            db.add(donation)
            db.commit()
            created += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            errors.append(f"Row {idx}: {exc}")
    return created, skipped_duplicates, skipped_invalid_dtn, errors
