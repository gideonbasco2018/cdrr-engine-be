from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.deps import get_remote_db

router = APIRouter(
    prefix="/fis",
    tags=["FIS Test Connection"]
)

@router.get("/test-connection")
def test_connection(db: Session = Depends(get_remote_db)):
    result = db.execute(text("SHOW TABLES")).fetchall()

    return {
        "status": "connected",
        "tables": [row[0] for row in result]
    }
