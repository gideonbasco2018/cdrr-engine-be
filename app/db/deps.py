from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.remote_session import RemoteSessionLocal

def get_remote_db():
    db = RemoteSessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSessionDep = Annotated[Session, Depends(get_remote_db)]