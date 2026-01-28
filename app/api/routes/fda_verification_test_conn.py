# app/api/routes/fda_eservices.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os
from dotenv import load_dotenv

from app.core.deps import get_current_active_user

load_dotenv()

router = APIRouter(
    prefix="/api/fda",
    tags=["FDA - Database Connection"],
    dependencies=[Depends(get_current_active_user)]  # 🔐 LOGIN REQUIRED BY DEFAULT
)

# Get the FDA eServices database URL from environment
REMOTE_FDA_ESERVICES_URL = os.getenv("REMOTE_FDA_ESERVICES_URL")


@router.get("/test-connection")
async def test_fda_eservices_connection():
    """
    Test endpoint to verify FDA eServices database connection
    """
    if not REMOTE_FDA_ESERVICES_URL:
        raise HTTPException(
            status_code=500,
            detail="REMOTE_FDA_ESERVICES_URL not configured in environment variables"
        )
    
    try:
        # Create engine for FDA eServices database
        engine = create_engine(
            REMOTE_FDA_ESERVICES_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=True
        )
        
        # Test the connection
        with engine.connect() as connection:
            # Execute a simple query to test connection
            result = connection.execute(text("SELECT 1 as test"))
            test_row = result.fetchone()
            
            # Get database name
            db_result = connection.execute(text("SELECT DATABASE() as db_name"))
            db_name = db_result.fetchone()[0]
            
            # Get server version
            version_result = connection.execute(text("SELECT VERSION() as version"))
            server_version = version_result.fetchone()[0]
            
            # Get table count
            tables_result = connection.execute(text(
                "SELECT COUNT(*) as table_count FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            ))
            table_count = tables_result.fetchone()[0]
        
        # Close the engine
        engine.dispose()
        
        return {
            "status": "success",
            "message": "✅ Successfully connected to FDA eServices database",
            "connection_test": test_row[0] == 1,
            "database_info": {
                "database_name": db_name,
                "server_version": server_version,
                "total_tables": table_count,
                "connection_url": REMOTE_FDA_ESERVICES_URL.split("@")[1] if "@" in REMOTE_FDA_ESERVICES_URL else "hidden"
            }
        }
        
    except SQLAlchemyError as e:
        error_message = str(e)
        
        # Provide more specific error messages
        if "Access denied" in error_message:
            detail = "❌ Access denied: Invalid username or password"
        elif "Can't connect" in error_message or "timed out" in error_message:
            detail = f"❌ Cannot connect to database server at {REMOTE_FDA_ESERVICES_URL.split('@')[1] if '@' in REMOTE_FDA_ESERVICES_URL else 'server'}"
        elif "Unknown database" in error_message:
            detail = "❌ Database does not exist on the server"
        else:
            detail = f"❌ Database connection error: {error_message}"
        
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": detail,
                "error_type": type(e).__name__,
                "error_details": error_message
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"❌ Unexpected error: {str(e)}",
                "error_type": type(e).__name__
            }
        )


@router.get("/list-tables")
async def list_fda_eservices_tables():
    """
    List all tables in the FDA eServices database
    """
    if not REMOTE_FDA_ESERVICES_URL:
        raise HTTPException(
            status_code=500,
            detail="REMOTE_FDA_ESERVICES_URL not configured in environment variables"
        )
    
    try:
        engine = create_engine(
            REMOTE_FDA_ESERVICES_URL,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        with engine.connect() as connection:
            # Get all tables in the database
            result = connection.execute(text(
                """
                SELECT 
                    TABLE_NAME as table_name,
                    TABLE_ROWS as estimated_rows,
                    ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) as size_mb
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                ORDER BY TABLE_NAME
                """
            ))
            
            tables = []
            for row in result:
                tables.append({
                    "table_name": row[0],
                    "estimated_rows": row[1],
                    "size_mb": float(row[2]) if row[2] else 0
                })
        
        engine.dispose()
        
        return {
            "status": "success",
            "total_tables": len(tables),
            "tables": tables
        }
        
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"❌ Failed to list tables: {str(e)}",
                "error_type": type(e).__name__
            }
        )


@router.get("/table-structure/{table_name}")
async def get_table_structure(table_name: str):
    """
    Get the structure of a specific table
    """
    if not REMOTE_FDA_ESERVICES_URL:
        raise HTTPException(
            status_code=500,
            detail="REMOTE_FDA_ESERVICES_URL not configured in environment variables"
        )
    
    try:
        engine = create_engine(
            REMOTE_FDA_ESERVICES_URL,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        with engine.connect() as connection:
            # Check if table exists
            table_check = connection.execute(text(
                f"""
                SELECT COUNT(*) as count
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                AND table_name = '{table_name}'
                """
            ))
            
            if table_check.fetchone()[0] == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Table '{table_name}' not found in database"
                )
            
            # Get table structure
            result = connection.execute(text(
                f"""
                SELECT 
                    COLUMN_NAME as column_name,
                    DATA_TYPE as data_type,
                    IS_NULLABLE as is_nullable,
                    COLUMN_KEY as column_key,
                    COLUMN_DEFAULT as default_value,
                    EXTRA as extra
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                AND table_name = '{table_name}'
                ORDER BY ORDINAL_POSITION
                """
            ))
            
            columns = []
            for row in result:
                columns.append({
                    "column_name": row[0],
                    "data_type": row[1],
                    "nullable": row[2] == "YES",
                    "key": row[3],
                    "default": row[4],
                    "extra": row[5]
                })
        
        engine.dispose()
        
        return {
            "status": "success",
            "table_name": table_name,
            "total_columns": len(columns),
            "columns": columns
        }
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"❌ Failed to get table structure: {str(e)}",
                "error_type": type(e).__name__
            }
        )