from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.deadline_checker import run_deadline_notifications  # ← BAGO
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
    notifications,  # ← BAGO
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
    expose_headers=["*"],
)

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
app.include_router(notifications.router)  # ← BAGO


@app.get("/")
def root():
    return {
        "message": "CDRR Engine API",
        "environment": settings.ENVIRONMENT,
        "docs_enabled": settings.DOCS_URL is not None,
    }
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from app.api.routes import (
#     auth, 
#     main_db, 
#     group, 
#     deck,
#     evaluation, 
#     application_logs,
#     doctrack,
#     analytics,
#     fda_verification_test_conn,
#     fda_verification
# )
# app = FastAPI(
#     title="CDRR ENGINE API",
#     description="API Description",
#     version="1.0.0",
#     docs_url="/docs",
#     redoc_url="/redoc",
#     openapi_url="/openapi.json"
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:5173",
#         "http://127.0.0.1:5173",
#         "http://localhost:3000",
#         "http://frontend:5173",
#         "*"
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )

# app.include_router(auth.router)
# app.include_router(main_db.router)
# app.include_router(group.router)
# app.include_router(deck.router)
# app.include_router(evaluation.router)
# app.include_router(application_logs.router)
# app.include_router(doctrack.router)
# app.include_router(analytics.router)
# app.include_router(fda_verification_test_conn.router)
# app.include_router(fda_verification.router)