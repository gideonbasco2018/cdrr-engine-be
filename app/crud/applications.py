from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Tuple

from app.models.application_logs import ApplicationLogs
from app.models.main_db import MainDB


def get_my_applications(
    db: Session,
    user_id: int,
) -> List[Tuple[ApplicationLogs, MainDB]]:
    """
    Returns all 'close' thread logs assigned to the given user,
    keeping only the latest log per application (highest del_index).
    """

    # Subquery: max del_index per main_db_id for this user
    subq = (
        db.query(
            ApplicationLogs.main_db_id,
            func.max(ApplicationLogs.del_index).label("max_del_index"),
        )
        .filter(
            ApplicationLogs.user_id == user_id,
            ApplicationLogs.del_thread == "close",
        )
        .group_by(ApplicationLogs.main_db_id)
        .subquery()
    )

    # Join back to get the actual log row + main_db data
    results = (
        db.query(ApplicationLogs, MainDB)
        .join(
            subq,
            (ApplicationLogs.main_db_id == subq.c.main_db_id)
            & (ApplicationLogs.del_index == subq.c.max_del_index),
        )
        .join(MainDB, MainDB.DB_ID == ApplicationLogs.main_db_id)
        .filter(
            ApplicationLogs.user_id == user_id,
            ApplicationLogs.del_thread == "close",
        )
        .order_by(ApplicationLogs.updated_at.desc())
        .all()
    )

    return results