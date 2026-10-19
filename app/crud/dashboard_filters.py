# app/crud/dashboard_filters.py

from app.models.application_logs import ApplicationLogs

# Rows in these threads are the only ones the dashboard counts.
COUNTED_THREADS = ["Close", "Open"]


def apply_counting_filters(q, user_id: int):
    """
    Single source of truth for which ApplicationLogs rows count on the dashboard.

    - Scoped by user_id (stable), never by user_name (users can rename).
    - Only del_thread 'Close' / 'Open'.
    - Rows created by a re-route or a re-assignment are NOT counted.
    """
    return q.filter(
        ApplicationLogs.user_id == user_id,
        ApplicationLogs.del_thread.in_(COUNTED_THREADS),
        ApplicationLogs.rerouted_at.is_(None),
        ApplicationLogs.rerouted_by_user_id.is_(None),
        ApplicationLogs.reassigned_at.is_(None),
        ApplicationLogs.reassigned_by_user_id.is_(None),
    )
