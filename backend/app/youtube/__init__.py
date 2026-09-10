from .client import YouTubeClient, YouTubeAPIError
from .scopes import (
    IDENTITY_SCOPES,
    REQUIRED_YOUTUBE_SCOPES,
    CANONICAL_OAUTH_SCOPES,
    get_scope_string,
    verify_granted_scopes,
)

__all__ = [
    "YouTubeClient",
    "YouTubeAPIError",
    "IDENTITY_SCOPES",
    "REQUIRED_YOUTUBE_SCOPES",
    "CANONICAL_OAUTH_SCOPES",
    "get_scope_string",
    "verify_granted_scopes",
]

