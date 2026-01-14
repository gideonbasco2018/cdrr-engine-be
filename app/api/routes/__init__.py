"""
API Routes
Include all route modules here
"""
from fastapi import APIRouter
from app.api.routes import auth, main_db  # Import all routers

api_router = APIRouter()

# Include auth routes
api_router.include_router(
    auth.router,
    tags=["Authentication"]
)

# Include main_db routes
api_router.include_router(
    main_db.router,
    tags=["Main Database"]
)