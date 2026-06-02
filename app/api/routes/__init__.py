"""
API Routes
Include all route modules here
"""
from fastapi import APIRouter
from app.api.routes import (
    auth, 
    main_db, 
    groups, 
    doctrack, 
    analytics, 
    fda_verification_test_conn, 
    fda_verification,
    fda_verification_statistics,
    menu_permissions,
    otc_test_conn,
    otc,
    cdrr_report,
    workflow_tasks,
    field_audit_log,
    notifications,
    bulk_upload_history,
    dashboard,
    applications,
    monitoring,
    spellcheck,
    closed_tasks,
    lead_assignment,
    cpr_correction,
    doc_type_released,
)
api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(groups.router)
api_router.include_router(main_db.router)
api_router.include_router(doctrack.router)
api_router.include_router(analytics.router)
api_router.include_router(fda_verification_test_conn.router)
api_router.include_router(fda_verification.router)
api_router.include_router(fda_verification_statistics.router)
api_router.include_router(menu_permissions.router)
api_router.include_router(otc_test_conn.router)
api_router.include_router(otc.router)
api_router.include_router(cdrr_report.router)
api_router.include_router(workflow_tasks.router)
api_router.include_router(field_audit_log.router)
api_router.include_router(notifications.router)
api_router.include_router(bulk_upload_history.router)
api_router.include_router(dashboard.router)
api_router.include_router(applications.router)
api_router.include_router(monitoring.router)
api_router.include_router(spellcheck.router)
api_router.include_router(closed_tasks.router)
api_router.include_router(lead_assignment.router)
api_router.include_router(cpr_correction.router)
api_router.include_router(doc_type_released.router)

 
