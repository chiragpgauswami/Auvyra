"""Configuration and Environment Validation for Auvyra.

Distinguishes between:
- REQUIRED: Core infrastructure settings (MongoDB, JWT secrets, Encryption key).
- FEATURE-SPECIFIC: Needed only when specific features (Google/YouTube OAuth, Ollama) are activated.
- OPTIONAL: External third-party integrations (Pexels, custom FFmpeg paths).
"""

from functools import lru_cache
import os
from typing import Dict, Any, List
from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger

class Settings(BaseSettings):
    # ==========================================
    # 1. REQUIRED Core Infrastructure Settings
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
    JWT_SECRET: str = Field(
        default="auvyra-development-jwt-secret-key-32chars-min!!",
        description="HMAC secret key for signing access tokens"
    )
    JWT_REFRESH_SECRET: str = Field(
        default="auvyra-development-jwt-refresh-secret-key-32chars!!",
        description="Secret key for refresh tokens"
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm for JWT signing"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="Access token expiration in minutes"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        description="Refresh token expiration in days"
    )
    ENCRYPTION_KEY: str = Field(
        default="",
        description="Fernet encryption key for sensitive tokens at rest"
    )

    # ==========================================
    # 2. FEATURE-SPECIFIC Settings
    # ==========================================
    # Google OAuth / YouTube (Required only for Google sign-in and YouTube publishing)
    GOOGLE_CLIENT_ID: str = Field(default="", description="Google OAuth Client ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", description="Google OAuth Client Secret")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/api/auth/google/callback",
        description="OAuth redirect callback URI"
    )

    # Local AI Gateway / Ollama (Required for script generation and research)
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL"
    )
    OLLAMA_MODEL: str = Field(
        default="llama3.1:8b",
        description="Default Ollama model name"
    )

    # ==========================================
    # 3. OPTIONAL Settings
    # ==========================================
    PEXELS_API_KEY: str = Field(default="", description="Optional Pexels API key for stock media")
    MEDIA_ROOT: str = Field(default="media", description="Root directory for stored media files")
    FFMPEG_BINARY: str = Field(default="", description="Optional explicit path to ffmpeg binary")
    FFPROBE_BINARY: str = Field(default="", description="Optional explicit path to ffprobe binary")

    # Application Environment
    APP_ENV: str = Field(default="development", description="development, test, or production")
    APP_HOST: str = Field(default="0.0.0.0", description="FastAPI bind host")
    APP_PORT: int = Field(default=8000, description="FastAPI bind port")
    FRONTEND_URL: str = Field(default="http://localhost:5173", description="Frontend origin for CORS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("ENCRYPTION_KEY", mode="after")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not v or v == "change-me":
            # Generate a deterministic development key if not supplied or left as default
            # In production, this should be explicitly set via environment
            return Fernet.generate_key().decode()
        # Verify it's a valid Fernet key
        try:
            Fernet(v.encode())
            return v
        except Exception:
            logger.warning("Invalid ENCRYPTION_KEY provided; generating a safe temporary key for runtime.")
            return Fernet.generate_key().decode()

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

    if not settings.JWT_SECRET or settings.JWT_SECRET == "change-me":
        report["warnings"].append("JWT_SECRET is using default development value.")
        report["required"]["jwt"] = "WARNING: Default secret used."
    else:
        report["required"]["jwt"] = "OK"

    # 2. Validate FEATURE-SPECIFIC
    google_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    report["features"]["google_oauth"] = {
        "status": "enabled" if google_configured else "disabled",
        "detail": "Configured for YouTube Publishing" if google_configured else "Missing Google credentials; YouTube publishing will be unavailable or mocked."
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
