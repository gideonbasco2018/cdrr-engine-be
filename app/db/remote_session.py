from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Existing remote engine (FIS)
remote_engine = create_engine(
    settings.REMOTE_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 10},
)

# FDA eServices engine
remote_fda_engine = create_engine(
    settings.REMOTE_FDA_ESERVICES_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 10},
)

# OTC engine (new)
remote_otc_engine = create_engine(
    settings.REMOTE_OTC_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 10},
)

RemoteSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=remote_engine,
)

RemoteFDASessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=remote_fda_engine,
)

RemoteOTCSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=remote_otc_engine,
)

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# import os

# REMOTE_DATABASE_URL = os.getenv("REMOTE_DATABASE_URL")

# remote_engine = create_engine(
#     REMOTE_DATABASE_URL,
#     pool_pre_ping=True,
#     pool_recycle=3600,
#     connect_args={"connect_timeout": 10},
# )

# RemoteSessionLocal = sessionmaker(
#     autocommit=False,
#     autoflush=False,
#     bind=remote_engine,
# )
