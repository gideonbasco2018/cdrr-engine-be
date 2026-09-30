# app/crud/rrdportal.py
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.schemas.rrdportal import CmdrApplicationOut, CmdrDelegationOut, CmdrProductOut


def _cols(model, exclude=()) -> str:
    """Build the SELECT list from the schema; backticks protect reserved words like ROW."""
    return ", ".join(f"`{n}`" for n in model.model_fields if n not in exclude)


# ======================= CMDR =======================
# Table names come ONLY from this whitelist, never from user input.
CMDR_TYPES: Dict[str, Dict[str, Any]] = {
    "initial": {
        "table": "PMT_CMDR_INITIAL",
        "product_table": "PMT_CMDR_INITIAL_PRODUCT",
        "missing": set(),
    },
    "initial_abridge": {
        "table": "PMT_CMDR_INITIAL_ABRIDGE",
        "product_table": "PMT_CMDR_INITIAL_PRODUCT_ABRIDGE",
        "missing": {"COMPANY_ADDRESS"},
    },
    "renewal": {
        "table": "PMT_CMDR_RENEWAL",
        "product_table": "PMT_CMDR_RENEWAL_PRODUCT",
        "missing": {"COMPANY_ADDRESS"},
    },
    "amendment": {
        "table": "PMT_CMDR_AMENDMENT",
        "product_table": "PMT_CMDR_AMENDMENT_PRODUCT",
        "missing": {"COMPANY_ADDRESS"},
    },
}

PRODUCT_COLS = _cols(CmdrProductOut)

# APP_DELEGATION is one-to-many per application. Joined on APP_UID
# (part of its PK, so lookups are indexed). APP_NUMBER would also work.
DELEGATION_TABLE = "APP_DELEGATION"
DELEGATION_COLS = _cols(
    CmdrDelegationOut
)  # DEL_DATA is not in the schema, so not selected


def _cfg(app_type: str) -> Dict[str, Any]:
    cfg = CMDR_TYPES[app_type]  # KeyError if not whitelisted
    return {**cfg, "cols": _cols(CmdrApplicationOut, cfg["missing"])}


def _union_cols(cfg: Dict[str, Any]) -> str:
    """Same column list/order for every table so UNION ALL lines up.
    Columns a table doesn't have (e.g. COMPANY_ADDRESS) become NULL."""
    parts = []
    for name in CmdrApplicationOut.model_fields:
        if name in cfg["missing"]:
            parts.append(f"NULL AS `{name}`")
        else:
            parts.append(f"`{name}`")
    return ", ".join(parts)


def _filters(
    search: Optional[str],
    app_status: Optional[str],
    type_application: Optional[str],
    application_option: Optional[str],
) -> Tuple[str, Dict[str, Any]]:
    """Build a WHERE clause (values are bound params, never f-stringed)."""
    conditions: List[str] = []
    params: Dict[str, Any] = {}

    if search:
        conditions.append(
            "(COMPANY_NAME LIKE :search OR DTN LIKE :search "
            "OR CAST(APP_NUMBER AS CHAR) LIKE :search)"
        )
        params["search"] = f"%{search}%"
    if app_status:
        conditions.append("APP_STATUS = :app_status")
        params["app_status"] = app_status
    if type_application:
        conditions.append("TYPE_APPLICATION = :type_application")
        params["type_application"] = type_application
    if application_option:
        conditions.append("APPLICATION_OPTION = :application_option")
        params["application_option"] = application_option

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


# ---------- children (one-to-many), batched to avoid N+1 queries ----------


def get_cmdr_delegations(db: Session, app_uid: str) -> List[Dict[str, Any]]:
    rows = (
        db.execute(
            text(
                f"SELECT {DELEGATION_COLS} FROM {DELEGATION_TABLE} "
                "WHERE APP_UID = :uid ORDER BY DEL_INDEX"
            ),
            {"uid": app_uid},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def _delegations_map(
    db: Session, app_uids: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    stmt = text(
        f"SELECT {DELEGATION_COLS} FROM {DELEGATION_TABLE} "
        "WHERE APP_UID IN :uids ORDER BY APP_UID, DEL_INDEX"
    ).bindparams(bindparam("uids", expanding=True))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in db.execute(stmt, {"uids": app_uids}).mappings().all():
        out.setdefault(r["APP_UID"], []).append(dict(r))
    return out


def _products_map(
    db: Session, app_type: str, app_uids: List[str]
) -> Dict[str, List[Dict[str, Any]]]:
    cfg = CMDR_TYPES[app_type]
    stmt = text(
        f"SELECT {PRODUCT_COLS} FROM {cfg['product_table']} "
        "WHERE APP_UID IN :uids ORDER BY APP_UID, `ROW`"
    ).bindparams(bindparam("uids", expanding=True))
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in db.execute(stmt, {"uids": app_uids}).mappings().all():
        out.setdefault(r["APP_UID"], []).append(dict(r))
    return out


def _attach_children(
    db: Session,
    items: List[Dict[str, Any]],
    include_products: bool,
    include_delegations: bool,
    app_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Add 'products' / 'delegations' to each item (null when not requested).
    app_type=None means items carry their own CMDR_TYPE (the /all list)."""
    for it in items:
        it["products"] = None
        it["delegations"] = None
    if not items or not (include_products or include_delegations):
        return items

    if include_delegations:
        dmap = _delegations_map(db, [i["APP_UID"] for i in items])
        for it in items:
            it["delegations"] = dmap.get(it["APP_UID"], [])

    if include_products:
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            by_type.setdefault(app_type or it["CMDR_TYPE"], []).append(it)
        for t, group in by_type.items():
            pmap = _products_map(db, t, [i["APP_UID"] for i in group])
            for it in group:
                it["products"] = pmap.get(it["APP_UID"], [])
    return items


# ---------- ALL types in one list (UNION ALL) ----------


def get_cmdr_all(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
    type_application: Optional[str] = None,
    application_option: Optional[str] = None,
    types: Optional[List[str]] = None,
    include_products: bool = False,
    include_delegations: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    keys = types or list(CMDR_TYPES)  # keys are whitelisted, safe to put in SQL
    where, params = _filters(search, app_status, type_application, application_option)

    selects: List[str] = []
    counts: List[str] = []
    for key in keys:
        cfg = CMDR_TYPES[key]
        selects.append(
            f"SELECT {_union_cols(cfg)}, '{key}' AS `CMDR_TYPE` "
            f"FROM {cfg['table']} {where}"
        )
        counts.append(f"SELECT COUNT(*) AS c FROM {cfg['table']} {where}")

    total = db.execute(
        text(f"SELECT SUM(c) FROM ({' UNION ALL '.join(counts)}) AS t"), params
    ).scalar()

    rows = (
        db.execute(
            text(
                f"SELECT * FROM ({' UNION ALL '.join(selects)}) AS u "
                "ORDER BY APP_NUMBER DESC LIMIT :limit OFFSET :skip"
            ),
            {**params, "skip": skip, "limit": limit},
        )
        .mappings()
        .all()
    )
    items = [dict(r) for r in rows]
    _attach_children(db, items, include_products, include_delegations)
    return items, int(total or 0)


def get_cmdr_filter_options(db: Session) -> Dict[str, List[str]]:
    """Distinct values across all CMDR tables, for filter dropdowns."""

    def distinct(col: str) -> List[str]:  # col is a hardcoded literal below
        union = " UNION ".join(
            f"SELECT {col} AS v FROM {cfg['table']}" for cfg in CMDR_TYPES.values()
        )
        rows = db.execute(
            text(
                f"SELECT v FROM ({union}) AS t WHERE v IS NOT NULL AND v <> '' ORDER BY v"
            )
        ).all()
        return [r[0] for r in rows]

    return {
        "cmdr_types": list(CMDR_TYPES),
        "type_application": distinct("TYPE_APPLICATION"),
        "application_option": distinct("APPLICATION_OPTION"),
        "app_status": distinct("APP_STATUS"),
    }


def get_cmdr_facets(
    db: Session,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
    type_application: Optional[str] = None,
    application_option: Optional[str] = None,
    types: Optional[List[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Counts per value for each filter (cascading: a facet ignores its own filter)."""
    base = " UNION ALL ".join(
        f"SELECT '{key}' AS CMDR_TYPE, APP_NUMBER, APP_STATUS, TYPE_APPLICATION, "
        f"APPLICATION_OPTION, COMPANY_NAME, DTN FROM {cfg['table']}"
        for key, cfg in CMDR_TYPES.items()  # keys/tables are whitelisted
    )
    columns = {  # facet name -> column (hardcoded, never user input)
        "cmdr_type": "CMDR_TYPE",
        "type_application": "TYPE_APPLICATION",
        "application_option": "APPLICATION_OPTION",
        "app_status": "APP_STATUS",
    }
    selected = {
        "cmdr_type": types,
        "type_application": type_application,
        "application_option": application_option,
        "app_status": app_status,
    }

    out: Dict[str, List[Dict[str, Any]]] = {}
    for name, col in columns.items():
        conditions = [f"{col} IS NOT NULL", f"{col} <> ''"]
        params: Dict[str, Any] = {}
        if search:
            conditions.append(
                "(COMPANY_NAME LIKE :search OR DTN LIKE :search "
                "OR CAST(APP_NUMBER AS CHAR) LIKE :search)"
            )
            params["search"] = f"%{search}%"
        expanding = False
        for other, ocol in columns.items():
            if other == name or not selected[other]:
                continue
            if other == "cmdr_type":
                conditions.append("CMDR_TYPE IN :types")
                params["types"] = selected[other]
                expanding = True
            else:
                conditions.append(f"{ocol} = :{other}")
                params[other] = selected[other]

        stmt = text(
            f"SELECT {col} AS v, COUNT(*) AS c FROM ({base}) AS u "
            f"WHERE {' AND '.join(conditions)} GROUP BY {col}"
        )
        if expanding:
            stmt = stmt.bindparams(bindparam("types", expanding=True))
        rows = db.execute(stmt, params).all()

        items = [{"value": str(r[0]), "count": int(r[1])} for r in rows]
        if name == "cmdr_type":
            order = list(CMDR_TYPES)
            items.sort(
                key=lambda i: order.index(i["value"]) if i["value"] in order else 99
            )
        else:
            items.sort(key=lambda i: i["value"])
        out[name] = items
    return out


# ---------- one type at a time ----------


def get_cmdr_list(
    db: Session,
    app_type: str,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    app_status: Optional[str] = None,
    type_application: Optional[str] = None,
    application_option: Optional[str] = None,
    include_products: bool = False,
    include_delegations: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
    cfg = _cfg(app_type)
    where, params = _filters(search, app_status, type_application, application_option)

    total = (
        db.execute(
            text(f"SELECT COUNT(*) FROM {cfg['table']} {where}"), params
        ).scalar()
        or 0
    )
    rows = (
        db.execute(
            text(
                f"SELECT {cfg['cols']} FROM {cfg['table']} {where} "
                "ORDER BY APP_NUMBER DESC LIMIT :limit OFFSET :skip"
            ),
            {**params, "skip": skip, "limit": limit},
        )
        .mappings()
        .all()
    )
    items = [dict(r) for r in rows]
    _attach_children(
        db, items, include_products, include_delegations, app_type=app_type
    )
    return items, total


def get_cmdr_application(
    db: Session, app_type: str, app_uid: str
) -> Optional[Dict[str, Any]]:
    cfg = _cfg(app_type)
    row = (
        db.execute(
            text(f"SELECT {cfg['cols']} FROM {cfg['table']} WHERE APP_UID = :uid"),
            {"uid": app_uid},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def get_cmdr_products(db: Session, app_type: str, app_uid: str) -> List[Dict[str, Any]]:
    cfg = _cfg(app_type)
    rows = (
        db.execute(
            text(
                f"SELECT {PRODUCT_COLS} FROM {cfg['product_table']} "
                "WHERE APP_UID = :uid ORDER BY `ROW`"
            ),
            {"uid": app_uid},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]
