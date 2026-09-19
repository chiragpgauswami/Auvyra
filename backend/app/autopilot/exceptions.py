"""
Autopilot Exception Hierarchy & Machine-Readable Error Codes.
Guarantees zero swallowed errors and structured failure telemetry across pipeline stages.
"""

from typing import Optional, Dict, Any

class AutopilotError(Exception):
    """Base error for all autopilot stage failures."""
    def __init__(
        self,
        message: str,
        code: str = "AUTOPILOT_ERROR",
        stage: str = "general",
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.stage = stage
        self.retryable = retryable
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "retryable": self.retryable,
            "details": self.details,
        }

class PexelsMediaError(AutopilotError):
    """Raised when suitable Pexels stock footage cannot be located or downloaded."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = True):
        super().__init__(
            message=message,
            code="PEXELS_NO_SUITABLE_MEDIA",
            stage="pexels",
            retryable=retryable,
            details=details
        )

class TTSError(AutopilotError):
    """Raised when Edge-TTS speech synthesis fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = True):
        super().__init__(
            message=message,
            code="TTS_FAILED",
            stage="tts",
            retryable=retryable,
            details=details
        )

class WhisperSubtitleError(AutopilotError):
    """Raised when faster-whisper speech transcription fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = True):
        super().__init__(
            message=message,
            code="WHISPER_FAILED",
            stage="subtitles",
            retryable=retryable,
            details=details
        )

class RenderError(AutopilotError):
    """Raised when FFmpeg video composition or encoding fails."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = False):
        super().__init__(
            message=message,
            code="RENDER_FAILED",
            stage="render",
            retryable=retryable,
            details=details
        )

class QAGateError(AutopilotError):
    """Raised when video fails QA verification and publishing must be strictly blocked."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="QA_FAILED",
            stage="qa",
            retryable=False,
            details=details
        )

class OAuthConfigurationError(AutopilotError):
    """Raised when YouTube credentials or scopes are missing or invalid."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="GOOGLE_OAUTH_NOT_CONFIGURED",
            stage="upload",
            retryable=False,
            details=details
        )

class PublishingError(AutopilotError):
    """Raised when YouTube Data API upload fails."""
    def __init__(self, message: str, code: str = "YOUTUBE_UPLOAD_FAILED", retryable: bool = True, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code=code,
            stage="upload",
            retryable=retryable,
            details=details
        )

