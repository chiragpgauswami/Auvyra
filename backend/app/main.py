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
from backend.app.api.autopilot import router as autopilot_router

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

import uuid

# Security Headers & Request ID Middleware
@app.middleware("http")
async def security_and_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sanitize_validation_errors(errors: list) -> list:
    """Sanitize validation error dictionaries to prevent non-serializable objects (such as raw bytes)
    from crashing JSON serialization and redact sensitive fields (passwords, secrets, tokens)."""
    sanitized = []
    for err in errors:
        if not isinstance(err, dict):
            sanitized.append({"msg": str(err), "type": "type_error"})
            continue

        loc = err.get("loc", ())
        loc_str = [str(item) for item in loc]
        is_sensitive = any(
            any(term in str(item).lower() for term in ("password", "token", "secret", "key", "authorization"))
            for item in loc
        )

        clean_item = {
            "loc": loc_str,
            "msg": err.get("msg", "Validation error"),
            "type": err.get("type", "value_error")
        }

        if is_sensitive:
            clean_item["input"] = "[REDACTED]"
        elif "input" in err:
            val = err["input"]
            if isinstance(val, (str, int, float, bool, type(None))):
                clean_item["input"] = val
            elif isinstance(val, bytes):
                clean_item["input"] = f"<bytes len={len(val)}>"
            elif isinstance(val, (list, tuple)):
                clean_item["input"] = f"<{type(val).__name__} len={len(val)}>"
            elif isinstance(val, dict):
                safe_keys = [k for k in val.keys() if not any(term in str(k).lower() for term in ("password", "token", "secret"))]
                clean_item["input"] = f"<dict keys={safe_keys}>"
            else:
                clean_item["input"] = f"<{type(val).__name__}>"

        sanitized.append(clean_item)
    return sanitized


# ==============================================================================
# Central Exception Handlers (Section 36 - Structured Error Standard)
# ==============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Format HTTPExceptions into structured error envelopes with request_id."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error_body = {
            "code": detail.get("code", "HTTP_ERROR"),
            "message": detail.get("message", "An error occurred"),
            "details": detail.get("details", None),
            "request_id": req_id
        }
    elif isinstance(detail, str):
        error_body = {
            "code": f"HTTP_{exc.status_code}",
            "message": detail,
            "details": None,
            "request_id": req_id
        }
    else:
        error_body = {
            "code": f"HTTP_{exc.status_code}",
            "message": "An error occurred",
            "details": detail,
            "request_id": req_id
        }

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_body},
        headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format request validation errors cleanly without stack traces or raw byte crashes."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    clean_details = sanitize_validation_errors(exc.errors())
    logger.warning(f"Request validation error on {request.url.path} [req_id={req_id}]: {clean_details}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload",
                "details": clean_details,
                "request_id": req_id
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions. Never leak python tracebacks to client."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.exception(f"Unhandled server exception on {request.method} {request.url.path} [req_id={req_id}]: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred",
                "details": None,
                "request_id": req_id
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
    ffmpeg_bin = getattr(settings, "FFMPEG_PATH", None) or getattr(settings, "FFMPEG_BINARY", None) or shutil.which("ffmpeg")
    ffprobe_bin = getattr(settings, "FFPROBE_BINARY", None) or shutil.which("ffprobe")
    
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


import os
from fastapi.staticfiles import StaticFiles

# ==============================================================================
# Mount API Routers & Static Media
# ==============================================================================
app.include_router(auth_router)
app.include_router(channels_router)
app.include_router(content_router)
app.include_router(research_router)
app.include_router(videos_router)
app.include_router(publishing_router)
app.include_router(analytics_router)
app.include_router(jobs_router)
app.include_router(autopilot_router)

# Mount local media directory for direct asset access
os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")

