import sys
from pathlib import Path
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.base_class import Base

from app.models.main_db import MainDB
from app.models.application_delegation import ApplicationDelegation
from app.models.application_logs import ApplicationLogs
from app.models.user import User
from app.models.group import Group
from app.models.user_groups import UserGroup
from app.models.menu_permissions import MenuItem, menu_group_permissions
from app.models.cdrr_report import CDRRReport, FROOReport, CDRRSecondary
from app.models.field_audit_log import ApplicationFieldAuditLog
from app.models.notification import Notification
from app.models.bulk_upload_history_records import BulkUploadHistoryRecord
from app.models.bulk_upload_history import BulkUploadHistory
from app.models.closed_tasks import ClosedTask
from app.models.lead_assignment import LeadAssignment
from app.models.application_document import ApplicationDocument
from app.models.bulk_upload_log import BulkUploadLog
from app.models.target_assignment import TargetAssignment
from app.models.directors_target import DirectorsTarget
from app.models.unit import Unit
from app.models.oauth_otp import OAuthOTP
from app.models.cpr_app_history import CPRAppHistory
from app.models.cpr_app_parties import CPRAppParty
from app.models.cpr_application import CPRApplication

config = context.config

# ---- SINGLE SOURCE OF TRUTH ----
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set")

# config.set_main_option("sqlalchemy.url", database_url)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
