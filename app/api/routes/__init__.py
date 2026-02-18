"""
API Routes
Include all route modules here
"""
from fastapi import APIRouter
from app.api.routes import (
    auth, 
    main_db, 
    groups, 
    deck, 
    evaluation, 
    doctrack, 
    analytics, 
    fda_verification_test_conn, 
    fda_verification,
    fda_verification_statistics,
    menu_permissions,
    otc_test_conn,
    otc,
    cdrr_report,
)
api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(groups.router)
api_router.include_router(main_db.router)
api_router.include_router(deck.router)
api_router.include_router(evaluation.router)
api_router.include_router(doctrack.router)
api_router.include_router(analytics.router)
api_router.include_router(fda_verification_test_conn.router)
api_router.include_router(fda_verification.router)
api_router.include_router(fda_verification_statistics.router)
api_router.include_router(menu_permissions.router)
api_router.include_router(otc_test_conn.router)
api_router.include_router(otc.router)
api_router.include_router(cdrr_report.router)



