"""
One-time backfill: put a user_id on every OPEN FGMP task row that only has a
user_name.

Why: FGMP task ownership now matches on user_id alone (see _assignee_match in
app/crud/gmp_logs.py). Rows created before user_id was captured — old Excel
imports, early deck logs, old self-loops — carry only a username. Without an
id they would match nobody once the name fallback is removed, so their task
would vanish from "My Tasks".

What it does:
  1. Snapshots every row it may touch into  gmp_application_logs_userid_bak
     (id, user_id, user_name, application_step, gmp_record_id, snapshot_at).
  2. For each OPEN row (del_thread='Open', del_last_index=1) with user_id IS
     NULL and a non-empty user_name:
       - exactly one ACTIVE user has that username  -> set user_id
       - zero, or more than one                     -> leave it, report it
  3. Prints a summary and the full list of rows it could NOT resolve — those
     need a manual reassign from the admin "unassigned tasks" view after the
     strict-id change ships.

Safe to run more than once. Dry-run by default.

    python -m scripts.backfill_gmp_log_user_ids            # dry run, no writes
    python -m scripts.backfill_gmp_log_user_ids --commit   # actually write

Rollback:
    UPDATE gmp_application_logs l
    JOIN gmp_application_logs_userid_bak b ON b.id = l.id
    SET l.user_id = b.user_id;              -- restores the pre-backfill state
"""
import argparse
import sys
from datetime import datetime

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.gmp_record import GMPApplicationLogs
from app.models.user import User

BAK_TABLE = "gmp_application_logs_userid_bak"


def _open_rows_missing_id(db):
    return (
        db.query(GMPApplicationLogs)
        .filter(
            GMPApplicationLogs.del_thread == "Open",
            GMPApplicationLogs.del_last_index == 1,
            GMPApplicationLogs.user_id.is_(None),
        )
        .all()
    )


def _snapshot(db, rows):
    db.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {BAK_TABLE} (
            id            BIGINT PRIMARY KEY,
            user_id       BIGINT NULL,
            user_name     VARCHAR(255) NULL,
            application_step VARCHAR(255) NULL,
            gmp_record_id BIGINT NULL,
            snapshot_at   DATETIME NULL
        )
    """))
    now = datetime.now()
    for r in rows:
        db.execute(
            text(f"""
                INSERT INTO {BAK_TABLE}
                    (id, user_id, user_name, application_step, gmp_record_id, snapshot_at)
                VALUES (:id, :uid, :uname, :step, :rec, :ts)
                ON DUPLICATE KEY UPDATE snapshot_at = VALUES(snapshot_at)
            """),
            {
                "id": r.id, "uid": r.user_id, "uname": r.user_name,
                "step": r.application_step, "rec": r.gmp_record_id, "ts": now,
            },
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = _open_rows_missing_id(db)
        print(f"Open task rows with no user_id: {len(rows)}")
        if not rows:
            print("Nothing to do.")
            return

        # Build username -> [active user ids] once.
        active = db.query(User).filter(User.is_active.is_(True)).all()
        by_name = {}
        for u in active:
            by_name.setdefault(u.username, []).append(u.id)

        resolved, ambiguous, unknown = [], [], []
        for r in rows:
            name = (r.user_name or "").strip()
            if not name:
                unknown.append(r)
                continue
            ids = by_name.get(name, [])
            if len(ids) == 1:
                resolved.append((r, ids[0]))
            elif len(ids) > 1:
                ambiguous.append(r)
            else:
                unknown.append(r)

        print(f"  will set user_id      : {len(resolved)}")
        print(f"  name matches >1 user  : {len(ambiguous)}")
        print(f"  name matches no user  : {len(unknown)}")

        def _dump(label, items):
            if not items:
                return
            print(f"\n--- {label} (need manual reassign) ---")
            for r in items:
                dtn = getattr(getattr(r, "gmp_record", None), "GMP_DTN", None)
                print(f"  log id={r.id}  DTN={dtn}  step={r.application_step}  user_name={r.user_name!r}")

        _dump("AMBIGUOUS", ambiguous)
        _dump("UNKNOWN", unknown)

        if not args.commit:
            print("\nDRY RUN — no changes written. Re-run with --commit to apply.")
            return

        _snapshot(db, rows)
        for r, uid in resolved:
            r.user_id = uid
        db.commit()
        print(f"\nDone. {len(resolved)} rows updated. Snapshot in {BAK_TABLE}.")
        if ambiguous or unknown:
            print(f"{len(ambiguous) + len(unknown)} rows still have no user_id — "
                  f"reassign them from the admin unassigned-tasks view.")
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
