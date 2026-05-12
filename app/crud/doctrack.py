from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# ------------------------
# Fetch document by RSN
# ------------------------
def get_document_by_rsn(db: Session, rsn: str) -> List[Dict[str, Any]]:
    query = text("""
        SELECT d.*, dc.docclassName
        FROM document_tracker.docreceivingtbl d
        LEFT JOIN document_tracker.docclassificationtbl dc
            ON d.docclassID = dc.docclassID
        WHERE d.RSN = :rsn
    """)
    result = db.execute(query, {"rsn": rsn}).mappings().all()
    return [dict(row) for row in result]


# ------------------------
# Fetch document log by docrecID
# ------------------------
def get_document_log_by_id(db: Session, docrecID: str) -> List[Dict[str, Any]]:
    query = text("""
        SELECT *
        FROM document_tracker.docreceivinglogtbl
        WHERE docrecID = :docrecID
    """)
    result = db.execute(query, {"docrecID": docrecID}).mappings().all()
    return result


# ------------------------
# Insert document log WITH userID (existing endpoint — unchanged)
# ------------------------
def insert_document_log(
    db: Session,
    docrecID: int,
    remarks: str,
    userID: int
) -> Optional[Dict[str, Any]]:
    """
    Insert a single document log into docreceivinglogtbl and return the inserted row.
    Used by: POST /log and POST /log/bulk
    session.py already sets time_zone='+08:00' on every connection,
    so NOW() returns PHT directly — no CONVERT_TZ needed.
    """
    insert_query = text("""
        INSERT INTO document_tracker.docreceivinglogtbl (docrecID, logdate, remarks, userID)
        VALUES (:docrecID, NOW(), :remarks, :userID)
    """)
    result = db.execute(insert_query, {"docrecID": docrecID, "remarks": remarks, "userID": userID})

    logID = result.lastrowid
    db.commit()

    if logID:
        row = db.execute(
            text("SELECT * FROM document_tracker.docreceivinglogtbl WHERE logID = :logID"),
            {"logID": logID}
        ).mappings().first()
        return dict(row) if row else None

    return None


# ------------------------
# Insert document log WITHOUT userID (used by upload-excel)
# ------------------------
def insert_document_log_no_user(
    db: Session,
    docrecID: int,
    remarks: str,
) -> Optional[Dict[str, Any]]:
    """
    Insert a single document log — no userID column.
    Used by: POST /upload-excel
    session.py already sets time_zone='+08:00' on every connection,
    so NOW() returns PHT directly — no CONVERT_TZ needed.
    """
    insert_query = text("""
        INSERT INTO document_tracker.docreceivinglogtbl (docrecID, logdate, remarks)
        VALUES (:docrecID, NOW(), :remarks)
    """)
    result = db.execute(insert_query, {"docrecID": docrecID, "remarks": remarks})

    logID = result.lastrowid
    db.commit()

    if logID:
        row = db.execute(
            text("SELECT * FROM document_tracker.docreceivinglogtbl WHERE logID = :logID"),
            {"logID": logID}
        ).mappings().first()
        return dict(row) if row else None

    return None


# ------------------------
# Bulk insert document logs (existing — unchanged)
# ------------------------
def insert_bulk_document_logs(
    db: Session,
    logs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    inserted_logs = []
    for log in logs:
        inserted = insert_document_log(
            db=db,
            docrecID=log["docrecID"],
            remarks=log["remarks"],
            userID=log["userID"]
        )
        if inserted:
            inserted_logs.append(inserted)
    return inserted_logs


# ------------------------
# Fetch document logs by multiple docrecIDs (existing — unchanged)
# ------------------------
def get_document_logs_by_ids(
    db: Session,
    docrecIDs: List[int]
) -> List[Dict[str, Any]]:
    if not docrecIDs:
        return []

    query = text(f"""
        SELECT *
        FROM document_tracker.docreceivinglogtbl
        WHERE docrecID IN ({', '.join([str(id) for id in docrecIDs])})
    """)
    result = db.execute(query).mappings().all()
    return [dict(row) for row in result]


# ------------------------
# Fetch docrecIDs by RSNs (existing — unchanged)
# ------------------------
def get_docrecIDs_by_rsns(
    db: Session,
    rsns: List[str]
) -> List[Dict[str, int]]:
    if not rsns:
        return []

    placeholders = ", ".join([f":rsn{i}" for i in range(len(rsns))])
    params       = {f"rsn{i}": rsn for i, rsn in enumerate(rsns)}

    query = text(f"""
        SELECT docrecID, RSN
        FROM document_tracker.docreceivingtbl
        WHERE RSN IN ({placeholders})
    """)
    result = db.execute(query, params).mappings().all()
    return [dict(row) for row in result]


# ------------------------
# Bulk insert by RSN + Remarks (used by upload-excel)
# ------------------------
def insert_bulk_logs_by_rsns(
    db: Session,
    entries: List[Dict[str, Any]],  # [{ "rsn": "...", "remarks": "..." }]
) -> Dict[str, Any]:
    """
    Given a list of { rsn, remarks } pairs from an Excel upload:
      1. Resolve all RSNs → docrecIDs in ONE bulk query (docreceivingtbl)
      2. Insert ONE new log row per Excel entry into docreceivinglogtbl
         columns: docrecID, logdate (NOW() in PHT), remarks — no userID
      3. Return inserted logs + failed entries with reasons
    """
    if not entries:
        return {"inserted": [], "failed": []}

    rsns = [e["rsn"] for e in entries]

    # Step 1: Bulk resolve RSN → docrecID
    rsn_records = get_docrecIDs_by_rsns(db, rsns)

    rsn_to_docrecid: Dict[str, int] = {}
    for row in rsn_records:
        rsn_to_docrecid[str(row["RSN"])] = row["docrecID"]

    inserted_logs:  List[Dict[str, Any]] = []
    failed_entries: List[Dict[str, Any]] = []

    # Step 2: Insert one log per Excel row
    for entry in entries:
        rsn      = entry["rsn"]
        remarks  = entry["remarks"]
        docrecID = rsn_to_docrecid.get(rsn)

        if not docrecID:
            failed_entries.append({
                "rsn":     rsn,
                "remarks": remarks,
                "reason":  "RSN not found in docreceivingtbl",
            })
            continue

        inserted = insert_document_log_no_user(db=db, docrecID=docrecID, remarks=remarks)

        if inserted:
            inserted_logs.append(inserted)
        else:
            failed_entries.append({
                "rsn":     rsn,
                "remarks": remarks,
                "reason":  f"Insert failed for docrecID {docrecID}",
            })

    return {"inserted": inserted_logs, "failed": failed_entries}

# ADD after insert_bulk_logs_by_rsns:

def insert_log_by_rsn_with_user(
    db: Session,
    rsn: str,
    remarks: str,
    userID: int,
) -> Optional[Dict[str, Any]]:
    """
    Resolve RSN → docrecID then insert a single log WITH userID.
    Used by: POST /log/by-rsn (ViewDetails + BulkDeck)
    """
    rsn_records = get_docrecIDs_by_rsns(db, [rsn])
    if not rsn_records:
        return None

    docrecID = rsn_records[0]["docrecID"]
    return insert_document_log(db=db, docrecID=docrecID, remarks=remarks, userID=userID)


def insert_bulk_logs_by_rsns_with_user(
    db: Session,
    entries: List[Dict[str, Any]],  # [{ "rsn": "...", "remarks": "...", "userID": int }]
) -> Dict[str, Any]:
    """
    Given a list of { rsn, remarks, userID } pairs:
      1. Resolve all RSNs → docrecIDs in ONE bulk query
      2. Insert one log per entry WITH userID
      3. Return inserted + failed with reasons
    """
    if not entries:
        return {"inserted": [], "failed": []}

    rsns = [e["rsn"] for e in entries]
    rsn_records = get_docrecIDs_by_rsns(db, rsns)

    rsn_to_docrecid: Dict[str, int] = {}
    for row in rsn_records:
        rsn_to_docrecid[str(row["RSN"])] = row["docrecID"]

    inserted_logs: List[Dict[str, Any]] = []
    failed_entries: List[Dict[str, Any]] = []

    for entry in entries:
        rsn = entry["rsn"]
        remarks = entry["remarks"]
        userID = entry["userID"]
        docrecID = rsn_to_docrecid.get(rsn)

        if not docrecID:
            failed_entries.append({
                "rsn": rsn,
                "remarks": remarks,
                "reason": "RSN not found in docreceivingtbl",
            })
            continue

        inserted = insert_document_log(
            db=db, docrecID=docrecID, remarks=remarks, userID=userID
        )

        if inserted:
            inserted_logs.append(inserted)
        else:
            failed_entries.append({
                "rsn": rsn,
                "remarks": remarks,
                "reason": f"Insert failed for docrecID {docrecID}",
            })

    return {"inserted": inserted_logs, "failed": failed_entries}