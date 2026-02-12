from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import (
    auth, 
    main_db, 
    groups, 
    deck,
    evaluation, 
    application_logs,
    doctrack,
    analytics,
    fda_verification_test_conn,
    fda_verification,
    fda_verification_statistics,
    menu_permissions,
    otc_test_conn,
    otc
)

# Dynamic docs URL based on environment
app = FastAPI(
    title="CDRR ENGINE API",
    description="API Description",
    version="1.0.0",
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL
)

# Dynamic CORS based on environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth.router)
app.include_router(main_db.router)
app.include_router(groups.router)
app.include_router(deck.router)
app.include_router(evaluation.router)
app.include_router(application_logs.router)
app.include_router(doctrack.router)
app.include_router(analytics.router)
app.include_router(fda_verification_test_conn.router)
app.include_router(fda_verification.router)
app.include_router(fda_verification_statistics.router)
app.include_router(menu_permissions.router)
app.include_router(otc_test_conn.router)
app.include_router(otc.router)

@app.get("/")
def root():
    return {
        "message": "CDRR Engine API",
        "environment": settings.ENVIRONMENT,
        "docs_enabled": settings.DOCS_URL is not None
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