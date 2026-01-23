"""
API Routes
Include all route modules here
"""
from fastapi import APIRouter
from app.api.routes import auth, main_db, group, deck, evaluation, doctrack, analytics

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(group.router)
api_router.include_router(main_db.router)
api_router.include_router(deck.router)
api_router.include_router(evaluation.router)
api_router.include_router(doctrack.router)
api_router.include_router(analytics.router)