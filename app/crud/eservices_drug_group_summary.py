# app/crud/eservices_drug_group_summary.py
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.eservices_drug_groups import DrugGroup

_WHITESPACE_RE = re.compile(r"\s+")

# Column in APPLICATION_LOGS that holds the current step of an application.
CURRENT_STEP_COLUMN = "application_step"

# Extra columns for the records drill-down. Used only by the records functions,
# so the summary query is unaffected. IMPORTANT: verify these two column names
# against the eServices schema (APPLICATION_INFO / PRODUCT_INFO).
RECORD_EXTRA_SELECT = """,
            ai.application_number       AS application_number,
            pi.brand_name               AS brand_name"""


def _clean_text(value: Optional[str]) -> str:
    """Collapse tabs, newlines and repeated spaces into single spaces and trim."""
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def _build_query(
    group: DrugGroup,
    application_status: str,
    application_step: Optional[str] = None,
    extra_select: str = "",
) -> Tuple[Any, Dict[str, str]]:
    """Build the raw rows query and its bound parameters for a drug group."""
    conditions: List[str] = []
    params: Dict[str, str] = {"application_status": application_status}

    for i, keyword in enumerate(group["category_keywords"]):
        key = f"cat_{i}"
        conditions.append(f"pi.pharmacologic_category LIKE :{key}")
        params[key] = f"%{keyword}%"

    for i, keyword in enumerate(group["generic_name_keywords"]):
        key = f"gen_{i}"
        conditions.append(f"pi.generic_name LIKE :{key}")
        params[key] = f"%{keyword}%"

    keyword_filter = "\n         OR ".join(conditions)

    # Optional filter on the current step of the latest log row.
    step_filter = ""
    if application_step:
        step_filter = f"AND TRIM(al.{CURRENT_STEP_COLUMN}) = :application_step"
        params["application_step"] = application_step

    query = text(f"""
        SELECT
            ai.application_id           AS application_id,
            pi.pharmacologic_category   AS pharmacologic_category,
            pi.generic_name             AS generic_name{extra_select}
        FROM APPLICATION_INFO ai
        INNER JOIN APPLICATION_PRODUCT ap
               ON ap.application_id = ai.application_id
        INNER JOIN PRODUCT_INFO pi
               ON pi.product_id = ap.product_id
        INNER JOIN APPLICATION_LOGS al
               ON al.application_id = ai.application_id
              AND al.id = (
                    SELECT MAX(l2.id)
                    FROM APPLICATION_LOGS l2
                    WHERE l2.application_id = ai.application_id
              )
        WHERE TRIM(al.application_status) = :application_status
          {step_filter}
          AND TRIM(ai.application_type) IN (
                'CLIDP Conversion',
                'Initial [CLIDP]',
                'Automatic Renewal [CLIDP]'
              )
          AND (
                {keyword_filter}
          )
        """)
    return query, params


def get_drug_group_summary(
    db: Session,
    group: DrugGroup,
    application_status: str,
    application_step: Optional[str] = None,
) -> Dict[str, Any]:
    """Return per-group counts plus overall totals for the given drug group and status.

    Rows are fetched at product level and grouped in Python so that names which
    differ only by whitespace, letter case or a known typo are merged, while
    application counts stay distinct.
    """
    query, params = _build_query(group, application_status, application_step)
    rows = db.execute(query, params).mappings().all()

    aliases = group["name_aliases"]
    group_by_generic_name = group["group_by_generic_name"]

    applications_by_key: Dict[Tuple[str, str], Set[Any]] = defaultdict(set)
    product_count_by_key: Counter = Counter()
    name_variants_by_key: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    category_variants_by_key: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    all_application_ids: Set[Any] = set()

    for row in rows:
        category = _clean_text(row["pharmacologic_category"])

        if group_by_generic_name:
            name = _clean_text(row["generic_name"])
            name = aliases.get(name.lower(), name)
        else:
            name = ""

        key = (category.lower(), name.lower())
        applications_by_key[key].add(row["application_id"])
        product_count_by_key[key] += 1
        name_variants_by_key[key][name] += 1
        category_variants_by_key[key][category] += 1
        all_application_ids.add(row["application_id"])

    items: List[Dict[str, Any]] = []
    for key, application_ids in applications_by_key.items():
        # Use the most common spelling as the display value.
        display_category = category_variants_by_key[key].most_common(1)[0][0]
        display_name = name_variants_by_key[key].most_common(1)[0][0]
        items.append(
            {
                "pharmacologic_category": display_category or None,
                "generic_name": display_name or None,
                "application_count": len(application_ids),
                "product_count": product_count_by_key[key],
            }
        )

    if group["sort_count_first"]:
        items.sort(
            key=lambda item: (
                -item["application_count"],
                (item["pharmacologic_category"] or "").lower(),
            )
        )
    else:
        items.sort(
            key=lambda item: (
                (item["pharmacologic_category"] or "").lower(),
                -item["application_count"],
            )
        )

    return {
        "total_application_count": len(all_application_ids),
        "total_product_count": len(rows),
        "items": items,
    }


# ══════════════════════════════════════════════════════════════════════
#  Records drill-down (click the total in the UI)
#  One row per product of the matching applications. Filtering, search and
#  paging run in Python so generic names match the cleaned / aliased values
#  that the breakdown table shows.
# ══════════════════════════════════════════════════════════════════════
def _fetch_product_rows(
    db: Session,
    group: DrugGroup,
    application_status: str,
    application_step: Optional[str] = None,
) -> List[Dict[str, Optional[str]]]:
    query, params = _build_query(
        group, application_status, application_step, RECORD_EXTRA_SELECT
    )
    aliases = group["name_aliases"]

    rows: List[Dict[str, Optional[str]]] = []
    for r in db.execute(query, params).mappings().all():
        name = _clean_text(r["generic_name"])
        name = aliases.get(name.lower(), name)
        app_no = r["application_number"]
        rows.append(
            {
                "application_number": (
                    None if app_no is None else str(app_no).strip() or None
                ),
                "generic_name": name or None,
                "brand_name": _clean_text(r["brand_name"]) or None,
            }
        )
    return rows


def get_drug_group_generic_names(
    db: Session,
    group: DrugGroup,
    application_status: str,
    application_step: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Distinct generic names (with product counts) for the multi-select filter."""
    rows = _fetch_product_rows(db, group, application_status, application_step)

    counts: Counter = Counter()
    variants: Dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        name = row["generic_name"]
        if not name:
            continue
        key = name.lower()
        counts[key] += 1
        variants[key][name] += 1

    items = [
        {"name": variants[key].most_common(1)[0][0], "count": count}
        for key, count in counts.items()
    ]
    items.sort(key=lambda item: item["name"].lower())
    return items


def get_drug_group_records(
    db: Session,
    group: DrugGroup,
    application_status: str,
    application_step: Optional[str] = None,
    search: Optional[str] = None,
    generic_names: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[Dict[str, Optional[str]]], int]:
    rows = _fetch_product_rows(db, group, application_status, application_step)

    if generic_names:
        wanted = {_clean_text(n).lower() for n in generic_names}
        rows = [r for r in rows if (r["generic_name"] or "").lower() in wanted]

    if search and search.strip():
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in (r["application_number"] or "").lower()
            or needle in (r["generic_name"] or "").lower()
            or needle in (r["brand_name"] or "").lower()
        ]

    rows.sort(
        key=lambda r: (
            (r["generic_name"] or "").lower(),
            (r["brand_name"] or "").lower(),
            r["application_number"] or "",
        )
    )

    total = len(rows)
    start = (page - 1) * page_size
    return rows[start : start + page_size], total
