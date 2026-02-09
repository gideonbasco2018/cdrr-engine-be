# app/db/session.py

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://cdrr_user:cdrr_password@mysql:3306/cdrr_engine")

# Create engine with UTC timezone enforcement
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "init_command": "SET time_zone='+00:00'"  # Force UTC
    },
    pool_pre_ping=True  # Check connection health
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Double check - event listener as backup
@event.listens_for(Engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Ensure UTC timezone on every connection"""
    with dbapi_conn.cursor() as cursor:
        cursor.execute("SET time_zone = '+00:00'")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()