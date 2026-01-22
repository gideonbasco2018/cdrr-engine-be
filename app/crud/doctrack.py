from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# ------------------------
# Fetch document by RSN
# ------------------------
def get_document_by_rsn(db: Session, rsn: str) -> List[Dict[str, Any]]:
    query = text("""
        SELECT *
        FROM document_tracker.docreceivingtbl
        WHERE RSN = :rsn
    """)
    result = db.execute(query, {"rsn": rsn}).mappings().all()
    return result


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
# Insert document log and return inserted row
# ------------------------
def insert_document_log(db: Session, docrecID: int, remarks: str, userID: int) -> Optional[Dict[str, Any]]:
    """
    Insert a single document log into docreceivinglogtbl and return the inserted row.
    """
    insert_query = text("""
        INSERT INTO document_tracker.docreceivinglogtbl (docrecID, logdate, remarks, userID)
        VALUES (:docrecID, NOW(), :remarks, :userID)
    """)
    params = {
        "docrecID": docrecID,
        "remarks": remarks,
        "userID": userID
    }

    db.execute(insert_query, params)
    db.commit()

    # Get last inserted ID
    last_id_result = db.execute(text("SELECT LAST_INSERT_ID() AS logID")).mappings().first()
    logID = last_id_result["logID"] if last_id_result else None

    # Fetch and return the inserted row
    if logID:
        result = db.execute(
            text("SELECT * FROM document_tracker.docreceivinglogtbl WHERE logID = :logID"),
            {"logID": logID}
        ).mappings().first()
        return dict(result) if result else None

    return None


# ------------------------
# Bulk insert document logs
# ------------------------
def insert_bulk_document_logs(db: Session, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Insert multiple document logs at once and return the inserted rows.
    """
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

def get_document_logs_by_ids(db: Session, docrecIDs: List[int]) -> List[Dict[str, Any]]:
    """
    Fetch document logs for multiple docrecIDs.
    """
    if not docrecIDs:
        return []

    query = text(f"""
        SELECT *
        FROM document_tracker.docreceivinglogtbl
        WHERE docrecID IN ({', '.join([str(id) for id in docrecIDs])})
    """)
    result = db.execute(query).mappings().all()
    return [dict(row) for row in result]

def get_docrecIDs_by_rsns(db: Session, rsns: List[str]) -> List[Dict[str, int]]:
    """
    Get all docrecIDs for the given list of RSNs.
    """
    if not rsns:
        return []

    query = text(f"""
        SELECT docrecID, RSN
        FROM document_tracker.docreceivingtbl
        WHERE RSN IN ({', '.join([':rsn' + str(i) for i in range(len(rsns))])})
    """)

    params = {f"rsn{i}": rsn for i, rsn in enumerate(rsns)}
    result = db.execute(query, params).mappings().all()

    return [dict(row) for row in result]