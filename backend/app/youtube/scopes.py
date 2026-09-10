"""Canonical OAuth Scopes for Auvyra YouTube and Google Integration.

Single source of truth for all OAuth authorization requests, token audits,
and permission checks across Auvyra.
"""

from typing import List

# Base identity and user profile scopes
IDENTITY_SCOPES: List[str] = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# Required YouTube scopes for channel automation, video upload, and analytics:
# - youtube.readonly: Required to fetch authenticated channel metadata (GET /channels?mine=true),
#                     custom URLs, subscriber counts, and playlists.
# - youtube.upload:   Required for resumable video uploading and metadata publishing.
# - yt-analytics.readonly: Required for fetching channel & video analytics reports.
REQUIRED_YOUTUBE_SCOPES: List[str] = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# Complete list of canonical scopes to request during OAuth authorization
CANONICAL_OAUTH_SCOPES: List[str] = IDENTITY_SCOPES + REQUIRED_YOUTUBE_SCOPES

def get_scope_string() -> str:
    """Return space-separated string of canonical scopes for OAuth requests."""
    return " ".join(CANONICAL_OAUTH_SCOPES)

def verify_granted_scopes(granted_scopes: List[str]) -> dict:
    """Check whether a list of granted scopes satisfies all required YouTube scopes."""
    normalized_granted = set(s.strip().rstrip("/") for s in granted_scopes)
    missing = []
    for req in REQUIRED_YOUTUBE_SCOPES:
        # Check direct match or broad scope match (e.g. youtube matches youtube.readonly)
        if req not in normalized_granted and "https://www.googleapis.com/auth/youtube" not in normalized_granted:
            missing.append(req)
            
    return {
        "valid": len(missing) == 0,
        "granted_count": len(granted_scopes),
        "missing_scopes": missing,
        "needs_reauthorization": len(missing) > 0
    }
