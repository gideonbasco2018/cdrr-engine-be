from fastapi import FastAPI
from app.api.routes import auth, main_db

# app = FastAPI(title="CDRR Engine API")
app = FastAPI(
    title="CDRR ENGINE API",           # Title sa Swagger
    description="API Description",     # Description
    version="1.0.0",                   # Version
    docs_url="/docs",                  # Swagger UI URL (default)
    redoc_url="/redoc",                # ReDoc URL (default)
    openapi_url="/openapi.json"        # OpenAPI schema URL
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(main_db.router) 