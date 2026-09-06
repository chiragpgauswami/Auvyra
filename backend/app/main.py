"""Auvyra FastAPI Application Factory with Health Checks and Structured Error Handling."""

import shutil
from contextlib import asynccontextmanager
from typing import Any, Dict

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from backend.app.config import get_settings
from backend.app.database import db_manager

# Import all API routers
from backend.app.auth.router import router as auth_router
from backend.app.api.channels import router as channels_router
from backend.app.api.content import router as content_router
from backend.app.api.research import router as research_router
from backend.app.api.videos import router as videos_router
from backend.app.api.publishing import router as publishing_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.jobs import router as jobs_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    logger.info("Initializing Auvyra backend...")
    
    # Connect to MongoDB
    try:
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_DATABASE}...")
        await db_manager.connect()
        logger.info("Connected to MongoDB. Creating indexes...")
        await db_manager.create_indexes()
        logger.info("MongoDB indexes verified.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB during startup: {e}")
        # Allow server to boot in degraded mode so health checks can report the status

    yield

    # Shutdown
    logger.info("Shutting down Auvyra backend...")
    try:
        await db_manager.disconnect()
        logger.info("Disconnected from MongoDB.")
    except Exception as e:
        logger.warning(f"Error during MongoDB disconnect: {e}")


app = FastAPI(
    title="Auvyra",
    description="AI-powered YouTube automation platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Central Exception Handlers (Section 36 - Structured Error Standard)
# ==============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Format HTTPExceptions into structured error envelopes."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error_body = {
            "code": detail.get("code", "HTTP_ERROR"),
            "message": detail.get("message", "An error occurred"),
            "details": detail.get("details", None)
        }
    elif isinstance(detail, str):
        error_body = {
            "code": f"HTTP_{exc.status_code}",
            "message": detail,
            "details": None
        }
    else:
        error_body = {
            "code": f"HTTP_{exc.status_code}",
            "message": "An error occurred",
            "details": detail
        }

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_body},
        headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format request validation errors cleanly without stack traces."""
    logger.warning(f"Request validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions. Never leak python tracebacks to client."""
    logger.exception(f"Unhandled server exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred",
                "details": None
            }
        }
    )


# ==============================================================================
# Health Check Endpoints (Section 6)
# ==============================================================================
async def check_mongodb_health() -> Dict[str, Any]:
    try:
        db = db_manager.get_database()
        await db.command("ping")
        return {"status": "ok", "database": settings.MONGODB_DATABASE}
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


async def check_ollama_health() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                configured_present = any(settings.OLLAMA_MODEL in m for m in models)
                return {
                    "status": "ok",
                    "url": settings.OLLAMA_BASE_URL,
                    "model_configured": settings.OLLAMA_MODEL,
                    "model_available": configured_present,
                    "available_models": models
                }
            return {"status": "degraded", "code": resp.status_code}
    except Exception:
        return {
            "status": "unavailable",
            "message": f"Ollama is not reachable at {settings.OLLAMA_BASE_URL}"
        }


def check_video_health() -> Dict[str, Any]:
    ffmpeg_bin = settings.FFMPEG_BINARY or shutil.which("ffmpeg")
    ffprobe_bin = settings.FFPROBE_BINARY or shutil.which("ffprobe")
    
    status_val = "ok" if (ffmpeg_bin and ffprobe_bin) else "unavailable"
    return {
        "status": status_val,
        "ffmpeg": ffmpeg_bin or "not found",
        "ffprobe": ffprobe_bin or "not found",
        "local_storage": str(settings.MEDIA_ROOT)
    }


@app.get("/api/health")
async def health_check():
    """Consolidated system health check endpoint."""
    mongo_health = await check_mongodb_health()
    ollama_health = await check_ollama_health()
    video_health = check_video_health()

    services = {
        "mongodb": mongo_health.get("status"),
        "ollama": ollama_health.get("status"),
        "ffmpeg": video_health.get("status")
    }

    # If any service is not ok, report degraded
    overall_status = "ok"
    if any(s != "ok" for s in services.values()):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "services": services
    }


@app.get("/api/health/mongodb")
async def health_mongodb():
    return await check_mongodb_health()


@app.get("/api/health/ollama")
async def health_ollama():
    return await check_ollama_health()


@app.get("/api/health/video")
async def health_video():
    return check_video_health()


# ==============================================================================
# Mount API Routers
# ==============================================================================
app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(content_router)
app.include_router(research_router)
app.include_router(videos_router)
app.include_router(publishing_router)
app.include_router(analytics_router)
app.include_router(jobs_router)
