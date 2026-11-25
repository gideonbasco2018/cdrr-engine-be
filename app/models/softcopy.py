# app/models/softcopy.py
"""Softcopy page: softcopies of letters CDRR-OD receives from FDAC.

The page keeps its work (letters, sorting, forwards) in the user's own
browser, not in the database. The only table is the download log:

  softcopy_downloads  one row per Excel / PDF file someone downloaded from
                      the page (transmittal files and the Export button):
                      who, when, file name, type, unit, how many letters
                      and the DTNs inside.

The table isn't created yet: the Alembic migration waits for approval.
"""
from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base_class import Base


class SoftcopyDownload(Base):
    __tablename__ = "softcopy_downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)          # "xlsx" | "pdf"
    kind = Column(String(20), nullable=False)               # "Transmittal" | "Export"
    unit = Column(String(100), nullable=True)               # transmittal target, or the Export's unit filter
    letter_count = Column(Integer, nullable=False, default=0)
    dtns = Column(JSON, nullable=False)                     # the DTNs inside the file
    downloaded_by = Column(String(150), nullable=True)      # alias, or username
    downloaded_by_user_id = Column(Integer, nullable=True, index=True)
    downloaded_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
