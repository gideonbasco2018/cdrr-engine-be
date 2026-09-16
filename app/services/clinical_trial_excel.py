# FILE: app/services/clinical_trial_excel.py
import io
import re
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.clinical_trial_columns import CLINICAL_TRIAL_COLUMNS, VALID_PHASES
from app.models.clinical_trial import ClinicalTrial
from app.schemas.clinical_trial import ClinicalTrialCreate

SHEET_NAME = "Clinical Trials"
HEADER_FILL = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)

# Accepted date formats for the "IL Initial Approval Date" column, tried in
# order. Uploaded files often come from ad-hoc trackers that don't follow the
# official template's YYYY-MM-DD format, so we accept a few common variants.
_DATE_FORMATS = [
    "%Y-%m-%d",  # 2026-06-01  (official template format)
    "%m/%d/%Y",  # 06/01/2026
    "%d/%m/%Y",  # 01/06/2026
    "%b %d, %Y",  # Sep 11, 2019
    "%B %d, %Y",  # September 11, 2019
    "%d-%b-%Y",  # 11-Sep-2019
    "%d %B %Y",  # 11 September 2019
    "%Y/%m/%d",  # 2026/06/01
    "%m-%d-%Y",  # 06-01-2026
]

# Maps a plain Arabic numeral phase (as seen in a lot of legacy trackers) to
# its Roman numeral equivalent.
_ARABIC_TO_ROMAN_PHASE = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
}

_PHASE_MAX_LEN = 10  # matches ClinicalTrial.phase column width


def _write_header(ws):
    for col_idx, column in enumerate(CLINICAL_TRIAL_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=column["label"])
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        ws.column_dimensions[get_column_letter(col_idx)].width = max(
            18, len(column["label"]) + 2
        )


def build_template_workbook() -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    _write_header(ws)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def _fill_merged_cells(ws) -> None:
    """
    Uploaded trackers frequently have merged cells (e.g. one Study Title or
    Sponsor Name cell spanning several rows). openpyxl only stores the value
    on the top-left cell of a merged range - every other cell in that range
    reads back as None via iter_rows(). Left as-is, this makes every row in
    the merge except the first look like it's missing that field.

    This unmerges every merged range on the sheet and copies the top-left
    cell's value into every cell that used to be part of it, so downstream
    parsing sees the real value on every row/column, not just the anchor.
    """
    merged_ranges = list(ws.merged_cells.ranges)
    for merged_range in merged_ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        top_left_value = ws.cell(row=min_row, column=min_col).value

        ws.unmerge_cells(str(merged_range))

        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                ws.cell(row=row, column=col, value=top_left_value)


# Excel's date epoch (serial number 1 = Jan 1, 1900, with Excel's
# well-known leap-year bug baked in - this offset matches how Excel
# and openpyxl both interpret serial dates).
_EXCEL_EPOCH = datetime(1899, 12, 30)


def _parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    # Some cells that are visually formatted as dates in the source file
    # aren't recognized as such by openpyxl and come through as a raw
    # numeric Excel serial date (e.g. 44757) instead of a datetime object.
    if isinstance(value, (int, float)):
        try:
            return (_EXCEL_EPOCH + timedelta(days=value)).date()
        except (OverflowError, ValueError):
            raise ValueError(f"Unrecognized date value: '{value}'")

    text = str(value).strip()
    if not text:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"Unrecognized date format: '{text}'. Expected YYYY-MM-DD " "(e.g. 2026-06-01)."
    )


def _parse_int(value) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, str):
        # Handles values like "4,800" that come from manually formatted sheets
        value = value.replace(",", "").strip()
        if not value:
            return 0
    return int(float(value))


def _clean_text(value) -> Optional[str]:
    """
    Normalize a raw Excel cell into a plain string, or None if empty.

    Excel silently stores numeric-looking values (e.g. a protocol number
    that happens to look like a number) as int/float instead of text. Left
    as-is, this makes Pydantic reject the row (protocol_no expects a str,
    not a float). This converts those back into text, dropping the
    spurious trailing ".0" that shows up for whole numbers.
    """
    if value is None:
        return None
    if isinstance(value, float):
        text = str(int(value)) if value.is_integer() else str(value)
    elif isinstance(value, int):
        text = str(value)
    else:
        text = str(value)
    text = text.strip()
    return text or None


def _normalize_phase(value) -> Optional[str]:
    """
    Best-effort normalization of the Phase column.

    Real trackers are inconsistent: some use Arabic numerals ("3" instead
    of "III"), some mark sub-phases ("2b" -> "IIb"), some list combined
    phases for adaptive studies ("I/II"), and some rows have garbage or
    misaligned data in this column entirely (a date, free text like
    "Epidemiological Study", etc).

    Rather than rejecting the whole row over a messy Phase cell, we
    normalize what we can recognize and leave anything else blank -
    Phase is not a required field.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Strip an optional "Phase" prefix (e.g. "Phase I" -> "I")
    text = re.sub(r"(?i)^phase\s*", "", text).strip()
    if not text:
        return None

    # Combined phases for adaptive studies, e.g. "I/II" or "2/3"
    if "/" in text:
        parts = [_normalize_phase(part) for part in text.split("/")]
        parts = [part for part in parts if part]
        result = "/".join(parts) if parts else None
        return result[:_PHASE_MAX_LEN] if result else None

    # Arabic numeral with an optional sub-phase letter, e.g. "2b" -> "IIb"
    match = re.match(r"^(\d+)\s*([a-zA-Z]?)$", text)
    if match:
        digit, suffix = match.groups()
        roman = _ARABIC_TO_ROMAN_PHASE.get(digit)
        if roman:
            result = f"{roman}{suffix.upper()}" if suffix else roman
            return result[:_PHASE_MAX_LEN]

    # Roman numeral already, with an optional sub-phase letter, e.g. "IIIb"
    text_upper = text.upper()
    if text_upper in VALID_PHASES:
        return text_upper
    match = re.match(r"^(I{1,3}|IV)([A-Z]?)$", text_upper)
    if match:
        roman, suffix = match.groups()
        result = f"{roman}{suffix}" if suffix else roman
        return result[:_PHASE_MAX_LEN]

    # Anything else (free text, a stray date from a misaligned row, etc.)
    # isn't a recognizable phase - leave it blank instead of failing the row.
    return None


def parse_upload_workbook(
    file_bytes: bytes,
) -> Tuple[List[Tuple[int, ClinicalTrialCreate]], List[str]]:
    """
    Returns (rows, errors), where rows is a list of (excel_row_number, data)
    pairs - the row number is kept so the caller can report which source
    row a later database-level error (e.g. a duplicate CT Reference Number)
    came from.
    """
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active

    _fill_merged_cells(ws)

    header_row = [cell.value for cell in ws[1]]
    expected_labels = [column["label"] for column in CLINICAL_TRIAL_COLUMNS]

    if header_row[: len(expected_labels)] != expected_labels:
        return [], [
            "Uploaded file does not match the official template headers. Please use Download Template."
        ]

    rows: List[Tuple[int, ClinicalTrialCreate]] = []
    errors: List[str] = []

    for row_idx, raw_row in enumerate(
        ws.iter_rows(min_row=2, values_only=True), start=2
    ):
        if raw_row is None or all(v is None or str(v).strip() == "" for v in raw_row):
            continue

        row_data = {}
        try:
            for col_idx, column in enumerate(CLINICAL_TRIAL_COLUMNS):
                value = raw_row[col_idx] if col_idx < len(raw_row) else None

                if column["field"] == "phase":
                    value = _normalize_phase(value)
                elif column["field"] == "il_approval_date":
                    value = _parse_date(value)
                elif column["field"] == "total_qty_approve":
                    value = _parse_int(value)
                else:
                    value = _clean_text(value)

                if column["required"] and (value is None or value == ""):
                    raise ValueError(f"'{column['label']}' is required")

                row_data[column["field"]] = value

            rows.append((row_idx, ClinicalTrialCreate(**row_data)))
        except Exception as exc:
            errors.append(f"Row {row_idx}: {exc}")

    return rows, errors


def build_export_workbook(trials: List[ClinicalTrial]) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    _write_header(ws)

    for row_idx, trial in enumerate(trials, start=2):
        for col_idx, column in enumerate(CLINICAL_TRIAL_COLUMNS, start=1):
            value = getattr(trial, column["field"])
            if isinstance(value, date):
                value = value.isoformat()
            ws.cell(row=row_idx, column=col_idx, value=value)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
