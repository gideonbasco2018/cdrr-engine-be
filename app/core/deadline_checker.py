# app/core/deadline_checker.py
#
# This runs automatically via APScheduler — no crontab needed.
# Add the scheduler setup to your main.py (see bottom of this file).

from datetime import date
from sqlalchemy.orm import Session

from app.db.session import SessionLocal          # adjust to your import
from app.schemas.notification import NotificationCreate
import app.crud.notification as crud_notif


def _get_dtn(log) -> str:
    """Extract DTN string from the related MainDB record."""
    try:
        return str(log.main_db.DB_DTN)   # adjust attribute name if different
    except Exception:
        return f"LOG#{log.id}"


def run_deadline_notifications():
    """
    Main cron function — called daily at 8:00 AM (Asia/Manila).

    Sends TWO types of notifications:
      1. 3 working days before deadline  → early warning
      2. On the deadline day itself      → urgent alert
    """
    db: Session = SessionLocal()
    today = date.today()
    created_count = 0

    print(f"[DeadlineChecker] Running — {today}")

    try:
        # ── Type 1: 3 working days away ────────────────────────────────
        approaching = crud_notif.get_approaching_deadline_logs(db, working_days_away=3)
        print(f"  Approaching (3 working days): {len(approaching)} record(s)")

        to_create = []
        for log in approaching:
            dtn = _get_dtn(log)

            if crud_notif.already_notified_today(db, log.user_name, dtn, title_like="3 Days"):
                print(f"  [SKIP] {log.user_name} / {dtn} — already notified")
                continue

            to_create.append(NotificationCreate(
                user_name  = log.user_name,
                title      = "⏰ Compliance Deadline in 3 Working Days",
                message    = (
                    f"DTN {dtn} has a compliance deadline on "
                    f"{log.deadline_date.strftime('%b %d, %Y')}. "
                    f"Please complete the required action before the deadline."
                ),
                link_dtn   = dtn,
                app_log_id = log.id,
            ))

        if to_create:
            created_count += crud_notif.bulk_create_notifications(db, to_create)

        # ── Type 2: Due TODAY ───────────────────────────────────────────
        due_today = crud_notif.get_due_today_logs(db)
        print(f"  Due today: {len(due_today)} record(s)")

        to_create_urgent = []
        for log in due_today:
            dtn = _get_dtn(log)

            if crud_notif.already_notified_today(db, log.user_name, dtn, title_like="TODAY"):
                print(f"  [SKIP] {log.user_name} / {dtn} — already notified (today)")
                continue

            to_create_urgent.append(NotificationCreate(
                user_name  = log.user_name,
                title      = "🚨 Compliance Deadline is TODAY",
                message    = (
                    f"DTN {dtn} compliance deadline is TODAY "
                    f"({log.deadline_date.strftime('%b %d, %Y')}). "
                    f"Immediate action is required."
                ),
                link_dtn   = dtn,
                app_log_id = log.id,
            ))

        if to_create_urgent:
            created_count += crud_notif.bulk_create_notifications(db, to_create_urgent)

        print(f"[DeadlineChecker] Done — {created_count} notification(s) created.")

    except Exception as e:
        print(f"[DeadlineChecker] ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# SETUP IN main.py  (APScheduler — runs INSIDE FastAPI, no crontab)
# ─────────────────────────────────────────────────────────────────────
#
# pip install apscheduler
#
# In your main.py:
#
#   from apscheduler.schedulers.background import BackgroundScheduler
#   from app.core.deadline_checker import run_deadline_notifications
#
#   scheduler = BackgroundScheduler(timezone="Asia/Manila")
#   scheduler.add_job(
#       run_deadline_notifications,
#       trigger="cron",
#       hour=8,
#       minute=0,
#       id="deadline_checker",
#       replace_existing=True,
#   )
#   scheduler.start()
#
#   app = FastAPI(lifespan=...)
#
#   @app.on_event("shutdown")
#   def shutdown_event():
#       scheduler.shutdown()
#
# ─────────────────────────────────────────────────────────────────────
# OPTIONAL: Manual trigger endpoint (for testing)
# Add to any router:
#
#   from app.core.deadline_checker import run_deadline_notifications
#
#   @router.post("/admin/trigger-deadline-check")
#   def trigger_deadline_check():
#       run_deadline_notifications()
#       return {"success": True, "message": "Deadline check triggered manually."}
#
# ─────────────────────────────────────────────────────────────────────