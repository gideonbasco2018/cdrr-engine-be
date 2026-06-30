# cdrr-engine/cdrr-engine-be/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request  
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.deadline_checker import run_deadline_notifications
from app.core.security import refresh_token_if_needed
from app.api.routes import (
    auth, 
    main_db, 
    groups, 
    application_logs,
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
    pdf_rename,
    frp_monitoring,
    application_document,
    duplicate_record,
)

# ── Scheduler setup ───────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="Asia/Manila")

scheduler.add_job(
    run_deadline_notifications,
    trigger="cron",
    hour=8,
    minute=0,
    id="deadline_checker",
    replace_existing=True,
)

# ── Lifespan (start/stop scheduler with the app) ─────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    print("[Scheduler] Started — deadline checker runs daily at 8:00 AM (Asia/Manila)")
    yield
    scheduler.shutdown()
    print("[Scheduler] Stopped.")

# ── FastAPI app ───────────────────────────────────────────────────────
app = FastAPI(
    title="CDRR ENGINE API",
    description="API Description",
    version="1.0.0",
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan,  # ← BAGO (replaces on_event)
)

# ── CORS ──────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-New-Token"], 
)

# ── Token Auto-Refresh Middleware ─────────────────────────────────────  ← BAGO
@app.middleware("http")
async def auto_refresh_token(request: Request, call_next):
    response = await call_next(request)
    
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    
    if token:
        new_token = refresh_token_if_needed(token)
        if new_token:
            response.headers["X-New-Token"] = new_token
    
    return response


# ── Routers ───────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(main_db.router)
app.include_router(groups.router)
app.include_router(application_logs.router)
app.include_router(doctrack.router)
app.include_router(analytics.router)
app.include_router(fda_verification_test_conn.router)
app.include_router(fda_verification.router)
app.include_router(fda_verification_statistics.router)
app.include_router(menu_permissions.router)
app.include_router(otc_test_conn.router)
app.include_router(otc.router)
app.include_router(cdrr_report.router)
app.include_router(workflow_tasks.router)
app.include_router(field_audit_log.router)
app.include_router(notifications.router)  
app.include_router(bulk_upload_history.router) 
app.include_router(dashboard.router) 
app.include_router(applications.router) 
app.include_router(monitoring.router) 
app.include_router(spellcheck.router) 
app.include_router(closed_tasks.router) 
app.include_router(lead_assignment.router) 
app.include_router(cpr_correction.router) 
app.include_router(doc_type_released.router)
app.include_router(pdf_rename.router)
app.include_router(frp_monitoring.router)
app.include_router(application_document.router)
app.include_router(duplicate_record.router)



@app.get("/")
def root():
    return {
        "message": "CDRR Engine API",
        "environment": settings.ENVIRONMENT,
        "docs_enabled": settings.DOCS_URL is not None,
    }
