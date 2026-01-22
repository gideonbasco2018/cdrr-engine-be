from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

REMOTE_DATABASE_URL = os.getenv("REMOTE_DATABASE_URL")

remote_engine = create_engine(
    REMOTE_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 10},
)

RemoteSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=remote_engine,
)
