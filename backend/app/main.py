import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import Base, engine
from app.api.routes import auth, applicants, applications, questionnaire, pd_sessions, admin, reports, ground_pd

logger = logging.getLogger(__name__)


class PollingEndpointFilter(logging.Filter):
    """
    Suppresses repetitive 200 OK access logs from continuous client-side polling
    endpoints (/live-state, /active, /health) to keep the terminal console clean
    and focused exclusively on necessary business logs, errors, and LangGraph runs.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.args and len(record.args) >= 5:
                status_code = record.args[4]
                path = str(record.args[2])
                if status_code == 200 and any(ep in path for ep in ("/live-state", "/active", "/health", "/questionnaire", "/applications")):
                    return False
        except Exception:
            pass

        msg = record.getMessage()
        if "200" in msg and any(ep in msg for ep in ("/live-state", "/active", "/health", "/questionnaire", "/applications")):
            return False
        return True


# Attach to uvicorn.access logger immediately
logging.getLogger("uvicorn.access").addFilter(PollingEndpointFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure filter is attached to uvicorn.access handlers after server bootstrap
    uv_access = logging.getLogger("uvicorn.access")
    uv_access.addFilter(PollingEndpointFilter())
    for h in uv_access.handlers:
        h.addFilter(PollingEndpointFilter())

    # Startup: ensure upload directories exist and models are registered
    settings.init_upload_directories()
    try:
        Base.metadata.create_all(bind=engine)
        from app.core.database import ensure_schema_migrations
        ensure_schema_migrations(engine)
    except Exception:
        # Graceful fallback when running in offline/testing environments
        pass
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="MSFincap Phase 1: In-Person Personal Discussion Underwriting & Verification Module",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"422 Validation Error on {request.method} {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


# CORS configuration for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media directory for serving uploaded recordings, photos, and PDF reports
settings.init_upload_directories()
app.mount(
    settings.MEDIA_BASE_URL,
    StaticFiles(directory=str(settings.UPLOAD_DIR)),
    name="media"
)

# Register API Routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(applicants.router, prefix="/applicants", tags=["applicants"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(questionnaire.router, prefix="/questionnaire", tags=["questionnaire"])
app.include_router(pd_sessions.router)
app.include_router(admin.router)
app.include_router(reports.router, prefix="/reports", tags=["reports"])
app.include_router(ground_pd.router)

# Also mount under /api/v1 prefix for client compatibility
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(applicants.router, prefix="/api/v1/applicants", tags=["applicants"])
app.include_router(applications.router, prefix="/api/v1/applications", tags=["applications"])
app.include_router(questionnaire.router, prefix="/api/v1/questionnaire", tags=["questionnaire"])
app.include_router(pd_sessions.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(ground_pd.router, prefix="/api/v1")


@app.get("/health", tags=["system"])
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "llm_provider": settings.LLM_PROVIDER
    }
