from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Separate Base so Alembic (internal MySQL) never picks up the external tables.
AppointmentBase = declarative_base()

if not settings.REMOTE_FDA_APPOINTMENT_SYSTEM_URL:
    raise RuntimeError("REMOTE_FDA_APPOINTMENT_SYSTEM_URL is not set")

appointment_engine = create_engine(
    settings.REMOTE_FDA_APPOINTMENT_SYSTEM_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    connect_args={"connect_timeout": 10},
)

AppointmentSessionLocal = sessionmaker(
    bind=appointment_engine, autocommit=False, autoflush=False
)


def get_appointment_db():
    db = AppointmentSessionLocal()
    try:
        yield db
    finally:
        db.close()
