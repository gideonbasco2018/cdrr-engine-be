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


def _clean_text(value: Optional[str]) -> str:
    """Collapse tabs, newlines and repeated spaces into single spaces and trim."""
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def _build_query(
    group: DrugGroup,
    application_status: str,
    application_step: Optional[str] = None,
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
            pi.generic_name             AS generic_name
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
