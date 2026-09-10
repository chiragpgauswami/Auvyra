"""Configuration and Environment Validation for Auvyra.

Distinguishes between:
- REQUIRED: Core infrastructure settings (MongoDB, JWT secrets, Encryption key).
- FEATURE-SPECIFIC: Needed only when specific features (Google/YouTube OAuth, Ollama) are activated.
- OPTIONAL: External third-party integrations (Pexels, custom FFmpeg paths).
"""

from functools import lru_cache
import os
import shutil
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger

class Settings(BaseSettings):
    # ==========================================
    # 1. Application Settings
    # ==========================================
    APP_NAME: str = Field(default="Auvyra", description="Application name")
    APP_ENV: str = Field(default="development", description="development, test, or production")
    APP_DEBUG: bool = Field(default=False, description="Enable debug mode (never in production)")
    APP_HOST: str = Field(default="0.0.0.0", description="FastAPI bind host")
    APP_PORT: int = Field(default=8000, description="FastAPI bind port")
    APP_URL: str = Field(default="http://localhost:8000", description="Backend base URL")
    FRONTEND_URL: str = Field(default="http://localhost:5173", description="Frontend origin for CORS")
    API_URL: str = Field(default="http://localhost:8000/api", description="API base URL")

    # ==========================================
    # 2. REQUIRED Core Security Settings
    # ==========================================
    JWT_SECRET: str = Field(
        default="auvyra-development-jwt-secret-key-32chars-min!!",
        description="HMAC secret key for signing access tokens",
        alias="JWT_SECRET_KEY"
    )
    JWT_REFRESH_SECRET: str = Field(
        default="auvyra-development-jwt-refresh-secret-key-32chars!!",
        description="Secret key for refresh tokens",
        alias="JWT_REFRESH_SECRET_KEY"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm for JWT signing"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration in minutes",
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration in days",
        alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS"
    )
    ENCRYPTION_KEY: str = Field(
        default="",
        description="Fernet encryption key for sensitive tokens at rest",
        alias="FERNET_ENCRYPTION_KEY"
    )
    COOKIE_SECURE: bool = Field(default=False, description="Enforce secure cookies over HTTPS")
    COOKIE_SAMESITE: str = Field(default="lax", description="SameSite cookie policy: lax, strict, none")

    # ==========================================
    # 3. Database Settings (Local or Atlas)
    # ==========================================
    MONGODB_URI: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection string (Atlas or local)"
    )
    MONGODB_DATABASE: str = Field(
        default="auvyra",
        description="Primary database name"
    )
    MONGODB_TEST_DATABASE: str = Field(
        default="auvyra_test",
        description="Isolated test database name"
    )

    # ==========================================
    # 4. Ollama Settings (Real AI Gateway)
    # ==========================================
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL"
    )
    OLLAMA_MODEL: str = Field(
        default="llama3.1:8b",
        description="Default Ollama model name"
    )
    OLLAMA_TIMEOUT_SECONDS: float = Field(
        default=60.0,
        description="Timeout for Ollama inference calls"
    )

    # ==========================================
    # 5. Google / YouTube OAuth
    # ==========================================
    GOOGLE_CLIENT_ID: str = Field(default="", description="Google OAuth Client ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", description="Google OAuth Client Secret")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/auth/google/callback",
        description="OAuth redirect callback URI"
    )
    YOUTUBE_API_KEY: str = Field(default="", description="Optional YouTube Data API key")
    YOUTUBE_CLIENT_ID: str = Field(default="", description="Alias for Google Client ID")
    YOUTUBE_CLIENT_SECRET: str = Field(default="", description="Alias for Google Client Secret")

    # ==========================================
    # 6. Storage Settings
    # ==========================================
    MEDIA_STORAGE_PROVIDER: str = Field(default="local", description="Storage backend: local or s3")
    MEDIA_ROOT: str = Field(default="media", description="Root directory for stored media files")

    # ==========================================
    # 7. Video Subsystem Settings
    # ==========================================
    FFMPEG_PATH: str = Field(
        default="",
        description="Explicit path to ffmpeg binary",
        alias="FFMPEG_BINARY"
    )
    FFPROBE_BINARY: str = Field(default="", description="Optional explicit path to ffprobe binary")
    VIDEO_WIDTH: int = Field(default=1080, description="Video width in pixels")
    VIDEO_HEIGHT: int = Field(default=1920, description="Video height in pixels")
    VIDEO_FPS: int = Field(default=30, description="Video rendering framerate")

    # ==========================================
    # 8. TTS Settings
    # ==========================================
    EDGE_TTS_VOICE: str = Field(default="en-US-AriaNeural", description="Default Edge TTS voice")
    EDGE_TTS_RATE: float = Field(default=1.0, description="Default Edge TTS speed multiplier")

    # ==========================================
    # 9. Worker Settings
    # ==========================================
    WORKER_POLL_INTERVAL: float = Field(default=2.0, description="Worker poll interval in seconds")
    WORKER_STALE_TIMEOUT: int = Field(default=15, description="Stale job recovery threshold in minutes")

    # ==========================================
    # 10. Research & Media Providers
    # ==========================================
    PEXELS_API_KEY: str = Field(default="", description="Optional Pexels API key for stock media")
    RESEARCH_PROVIDERS: str = Field(default="", description="Configured research external provider names")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True
    )

    @field_validator("ENCRYPTION_KEY", mode="after")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not v or v == "change-me" or v == "your-fernet-key-change-this":
            # Generate a development key if not supplied
            return Fernet.generate_key().decode()
        try:
            Fernet(v.encode())
            return v
        except Exception:
            logger.warning("Invalid ENCRYPTION_KEY provided; generating a safe temporary key for runtime.")
            return Fernet.generate_key().decode()

    @model_validator(mode="after")
    def validate_production_guards(self) -> "Settings":
        if self.APP_ENV == "production":
            self.APP_DEBUG = False
            self.COOKIE_SECURE = True
            
            # Guard default secrets
            default_secrets = [
                "auvyra-development-jwt-secret-key-32chars-min!!",
                "change-me",
                "your-secret-key-change-this"
            ]
            if self.JWT_SECRET in default_secrets or len(self.JWT_SECRET) < 32:
                raise ValueError("Production security violation: JWT_SECRET_KEY must be a unique secret with at least 32 characters.")
            if not self.MONGODB_URI:
                raise ValueError("Production configuration violation: MONGODB_URI is required in production.")
        return self

    @property
    def ffmpeg_bin(self) -> str:
        return self.FFMPEG_PATH or shutil.which("ffmpeg") or "ffmpeg"

    @property
    def ffprobe_bin(self) -> str:
        return self.FFPROBE_BINARY or shutil.which("ffprobe") or "ffprobe"

    def get_fernet(self) -> Fernet:
        return Fernet(self.ENCRYPTION_KEY.encode())


def validate_environment(settings: Settings) -> Dict[str, Any]:
    """Validate startup configuration and categorize status into REQUIRED, FEATURE-SPECIFIC, and OPTIONAL."""
    report: Dict[str, Any] = {
        "valid": True,
        "required": {},
        "features": {},
        "optional": {},
        "warnings": []
    }

    # 1. Validate REQUIRED
    if not settings.MONGODB_URI:
        report["valid"] = False
        report["required"]["mongodb"] = "MISSING: MONGODB_URI is required."
    else:
        report["required"]["mongodb"] = "OK"

    default_secrets = [
        "auvyra-development-jwt-secret-key-32chars-min!!",
        "change-me",
        "your-secret-key-change-this"
    ]
    if settings.JWT_SECRET in default_secrets:
        if settings.APP_ENV == "production":
            report["valid"] = False
            report["required"]["jwt"] = "FAIL: Default JWT_SECRET is prohibited in production."
        else:
            report["warnings"].append("JWT_SECRET is using default development key.")
            report["required"]["jwt"] = "WARNING: Default secret used."
    else:
        report["required"]["jwt"] = "OK"

    # 2. Validate FEATURE-SPECIFIC
    google_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    report["features"]["google_oauth"] = {
        "status": "enabled" if google_configured else "disabled",
        "detail": "Configured for YouTube Publishing" if google_configured else "Missing Google credentials; YouTube publishing will be BLOCKED."
    }

    report["features"]["ollama"] = {
        "status": "configured",
        "url": settings.OLLAMA_BASE_URL,
        "model": settings.OLLAMA_MODEL
    }

    # 3. Validate OPTIONAL
    report["optional"]["pexels"] = {
        "status": "configured" if settings.PEXELS_API_KEY else "disabled",
        "detail": "Pexels stock media enabled" if settings.PEXELS_API_KEY else "Using local-first media generation"
    }

    return report


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    validation = validate_environment(settings)
    for warning in validation.get("warnings", []):
        logger.warning(f"[CONFIG] {warning}")
    return settings
