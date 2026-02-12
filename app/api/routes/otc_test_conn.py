# app/api/routes/otc_test_conn.py

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.remote_session import remote_otc_engine

router = APIRouter()

@router.get("/test-otc-connection")
async def test_otc_connection():
    """
    Test connection to remote OTC database (wf_cdrr)
    """
    try:
        with remote_otc_engine.connect() as connection:
            # Test basic connection
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            
            # Get database name to confirm
            db_result = connection.execute(text("SELECT DATABASE()"))
            db_name = db_result.fetchone()[0]
            
            # Optional: Get table count
            tables_result = connection.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :db"),
                {"db": db_name}
            )
            table_count = tables_result.fetchone()[0]
            
            return {
                "status": "success",
                "message": "OTC database connection successful",
                "database": db_name,
                "table_count": table_count,
                "connection_info": {
                    "host": remote_otc_engine.url.host,
                    "port": remote_otc_engine.url.port,
                    "database": remote_otc_engine.url.database
                }
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Failed to connect to OTC database",
                "error": str(e)
            }
        )