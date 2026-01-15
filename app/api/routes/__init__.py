"""
API Routes
Include all route modules here
"""
from fastapi import APIRouter
from app.api.routes import auth, main_db, group

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(group.router)
api_router.include_router(main_db.router)