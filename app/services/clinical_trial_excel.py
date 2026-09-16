# FILE: app/services/clinical_trial_excel.py
import io
import re
from datetime import date, datetime
from typing import List, Tuple

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


def _parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

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


def _normalize_phase(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    # Strip an optional "Phase" prefix (e.g. "Phase I" -> "I") and normalize
    # case, since trackers don't always follow the template exactly.
    text = re.sub(r"(?i)^phase\s*", "", text).strip()
    return text.upper()


def parse_upload_workbook(
    file_bytes: bytes,
) -> Tuple[List[ClinicalTrialCreate], List[str]]:
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    ws = wb.active

    _fill_merged_cells(ws)

    header_row = [cell.value for cell in ws[1]]
    expected_labels = [column["label"] for column in CLINICAL_TRIAL_COLUMNS]

    if header_row[: len(expected_labels)] != expected_labels:
        return [], [
            "Uploaded file does not match the official template headers. Please use Download Template."
        ]

    rows: List[ClinicalTrialCreate] = []
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
                elif isinstance(value, str):
                    value = value.strip() or None

                if column["required"] and (value is None or value == ""):
                    raise ValueError(f"'{column['label']}' is required")

                row_data[column["field"]] = value

            phase_value = row_data.get("phase")
            if phase_value and phase_value not in VALID_PHASES:
                raise ValueError(
                    f"Phase must be one of {VALID_PHASES} "
                    f"(got '{raw_row[2] if len(raw_row) > 2 else ''}')"
                )
            if not phase_value:
                row_data["phase"] = None

            rows.append(ClinicalTrialCreate(**row_data))
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
