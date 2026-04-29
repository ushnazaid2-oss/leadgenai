"""
FastAPI Application Entry Point.
Mounts all routers, middleware, static files, and initializes the database.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, close_db
from app.middleware.logging_middleware import setup_logging, RequestLoggingMiddleware
from app.middleware.rate_limiter import limiter

# Optional Sentry integration
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    setup_logging(settings.LOG_LEVEL)
    logging.getLogger(__name__).info("Starting LeadGenAI Outreach Agent...")
    await init_db()
    logging.getLogger(__name__).info("Database initialized")
    yield
    await close_db()
    logging.getLogger(__name__).info("Shutdown complete")


app = FastAPI(
    title="LeadGenAI — Hybrid Outreach Agent",
    description="Multi-channel outreach platform with Email, WhatsApp, AI Voice Calling, and CRM",
    version="1.0.0",
    lifespan=lifespan,
)

# --- Middleware ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
from app.api.auth import router as auth_router
from app.api.leads import router as leads_router
from app.api.campaigns import router as campaigns_router
from app.api.email import router as email_router
from app.api.whatsapp import router as whatsapp_router
from app.api.calls import router as calls_router
from app.api.analytics import router as analytics_router
from app.api.tracking import router as tracking_router

app.include_router(auth_router)
app.include_router(leads_router)
app.include_router(campaigns_router)
app.include_router(email_router)
app.include_router(whatsapp_router)
app.include_router(calls_router)
app.include_router(analytics_router)
app.include_router(tracking_router)

# --- Static Files (Dashboard Frontend) ---
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "modules": {
            "email": settings.FEATURE_EMAIL_ENABLED,
            "whatsapp": settings.FEATURE_WHATSAPP_ENABLED,
            "calls": settings.FEATURE_CALLS_ENABLED,
        },
    }
