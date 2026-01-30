from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    # App Settings
    APP_NAME = os.getenv("APP_NAME", "CDRR Engine")
    APP_ENV = os.getenv("APP_ENV", "development")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    
    # API Documentation - controlled via environment variables
    _docs_url = os.getenv("DOCS_URL", "/docs")
    _redoc_url = os.getenv("REDOC_URL", "/redoc")
    _openapi_url = os.getenv("OPENAPI_URL", "/openapi.json")
    
    # Convert string "None" or empty string to actual None
    DOCS_URL = None if _docs_url in ["None", ""] else _docs_url
    REDOC_URL = None if _redoc_url in ["None", ""] else _redoc_url
    OPENAPI_URL = None if _openapi_url in ["None", ""] else _openapi_url
    
    # CORS Origins
    _base_cors = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://frontend:5173",
    ]
    
    # Build CORS origins based on environment
    if ENVIRONMENT == "development":
        CORS_ORIGINS = _base_cors + ["*"]
    else:
        # Production - add specific domains from env
        custom_origins = os.getenv("CORS_ORIGINS", "")
        if custom_origins:
            CORS_ORIGINS = _base_cors + [o.strip() for o in custom_origins.split(",")]
        else:
            CORS_ORIGINS = _base_cors
    
    # Database
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    
    # Remote Databases
    REMOTE_DATABASE_URL = os.getenv("REMOTE_DATABASE_URL")
    REMOTE_FDA_ESERVICES_URL = os.getenv("REMOTE_FDA_ESERVICES_URL")

settings = Settings()


# from dotenv import load_dotenv
# import os

# load_dotenv()

# class Settings:
#     APP_NAME = os.getenv("APP_NAME")
#     APP_ENV = os.getenv("APP_ENV")

#     DB_HOST = os.getenv("DB_HOST")
#     DB_PORT = os.getenv("DB_PORT")
#     DB_USER = os.getenv("DB_USER")
#     DB_PASSWORD = os.getenv("DB_PASSWORD")
#     DB_NAME = os.getenv("DB_NAME")

#     DATABASE_URL = (
#         f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
#         f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
#     )

# settings = Settings()
