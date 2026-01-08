from app.core.database import engine
from sqlalchemy import text

def test_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
            print(f"Result: {result.fetchone()}")
            
            # Check existing tables
            result = connection.execute(text("SHOW TABLES"))
            tables = result.fetchall()
            print(f"\n📊 Existing tables in database:")
            for table in tables:
                print(f"  - {table[0]}")
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    test_connection()