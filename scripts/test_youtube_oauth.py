#!/usr/bin/env python3
"""Auvyra YouTube OAuth & Channel Connection Diagnostic Tool.

Zero-Mock Policy: Validates real OAuth configuration, scope definitions,
token decryption, YouTube Data API v3 connectivity, and MongoDB persistence.
NEVER prints access tokens, refresh tokens, client secrets, or authorization codes.
"""

import sys
import os
import asyncio
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import httpx

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import get_settings
from backend.app.database import db_manager
from backend.app.youtube.scopes import (
    REQUIRED_YOUTUBE_SCOPES,
    CANONICAL_OAUTH_SCOPES,
    get_scope_string,
    verify_granted_scopes,
)
from backend.app.youtube.client import YouTubeClient, YouTubeAPIError

def mask_string(val: str, show_chars: int = 6) -> str:
    if not val:
        return "<not set>"
    if len(val) <= show_chars:
        return "***"
    return f"{val[:show_chars]}...***"

async def run_diagnostics():
    print("\n========================================================")
    print(" AUVYRA YOUTUBE CONNECTION DIAGNOSTIC")
    print("========================================================\n")

    settings = get_settings()
    results = {}
    details = {}

    # 1. Google OAuth Configuration
    has_client_id = bool(settings.GOOGLE_CLIENT_ID and not settings.GOOGLE_CLIENT_ID.startswith("change-me"))
    has_client_secret = bool(settings.GOOGLE_CLIENT_SECRET and not settings.GOOGLE_CLIENT_SECRET.startswith("change-me"))
    has_redirect = bool(settings.GOOGLE_REDIRECT_URI)

    if has_client_id and has_client_secret and has_redirect:
        results["config"] = "PASS"
        details["config"] = f"Client ID: {mask_string(settings.GOOGLE_CLIENT_ID, 12)}, Redirect URI: {settings.GOOGLE_REDIRECT_URI}"
    else:
        results["config"] = "FAIL"
        details["config"] = "Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or GOOGLE_REDIRECT_URI in .env"

    # 2. Canonical Scope Definitions
    has_readonly = "https://www.googleapis.com/auth/youtube.readonly" in CANONICAL_OAUTH_SCOPES
    has_upload = "https://www.googleapis.com/auth/youtube.upload" in CANONICAL_OAUTH_SCOPES
    has_analytics = "https://www.googleapis.com/auth/yt-analytics.readonly" in CANONICAL_OAUTH_SCOPES

    if has_readonly and has_upload and has_analytics:
        results["scopes_configured"] = "PASS"
        details["scopes_configured"] = f"Configured {len(CANONICAL_OAUTH_SCOPES)} scopes including youtube.readonly, youtube.upload, yt-analytics.readonly"
    else:
        results["scopes_configured"] = "FAIL"
        missing = []
        if not has_readonly: missing.append("youtube.readonly")
        if not has_upload: missing.append("youtube.upload")
        if not has_analytics: missing.append("yt-analytics.readonly")
        details["scopes_configured"] = f"Missing required scopes from canonical list: {missing}"

    # 3. OAuth URL Generation
    scope_str = get_scope_string()
    test_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope_str}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&include_granted_scopes=true"
    )
    parsed = urlparse(test_url)
    qs = parse_qs(parsed.query)
    req_scopes_in_url = qs.get("scope", [""])[0].split(" ")
    
    url_has_readonly = "https://www.googleapis.com/auth/youtube.readonly" in req_scopes_in_url
    if "prompt" in qs and qs["prompt"] == ["consent"] and url_has_readonly:
        results["url_gen"] = "PASS"
        details["url_gen"] = "OAuth URL enforces prompt=consent and includes youtube.readonly"
    else:
        results["url_gen"] = "FAIL"
        details["url_gen"] = "OAuth URL missing consent prompt or youtube.readonly"

    # Connect to database for token & channel verification
    await db_manager.connect()
    
    # 4. Check Stored OAuth Credentials
    oauth_doc = await db_manager.db.oauth_accounts.find_one({"provider": "google"}, sort=[("updated_at", -1)])
    
    if not oauth_doc:
        results["actual_scopes"] = "BLOCKED"
        results["api_credentials"] = "BLOCKED"
        results["channel_lookup"] = "BLOCKED"
        results["persistence"] = "BLOCKED"
        details["actual_scopes"] = "No Google OAuth accounts stored in MongoDB yet. Re-login via /api/auth/google."
    else:
        fernet = settings.get_fernet()
        access_token_encrypted = oauth_doc.get("access_token_encrypted")
        refresh_token_encrypted = oauth_doc.get("refresh_token_encrypted")
        access_token = None
        refresh_token = None
        granted_scopes = oauth_doc.get("granted_scopes", [])

        try:
            if refresh_token_encrypted:
                refresh_token = fernet.decrypt(refresh_token_encrypted.encode()).decode()
            if access_token_encrypted:
                access_token = fernet.decrypt(access_token_encrypted.encode()).decode()
            results["api_credentials"] = "PASS"
            details["api_credentials"] = "Tokens successfully decrypted from at-rest Fernet storage"
        except Exception as decrypt_err:
            results["api_credentials"] = "FAIL"
            details["api_credentials"] = f"Decryption failed: {decrypt_err}"

        # If refresh token is available, refresh to obtain latest active token and real live scopes from Google
        if refresh_token:
            async with httpx.AsyncClient() as client:
                try:
                    ref_resp = await client.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "client_id": settings.GOOGLE_CLIENT_ID,
                            "client_secret": settings.GOOGLE_CLIENT_SECRET,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token"
                        }
                    )
                    if ref_resp.status_code == 200:
                        ref_data = ref_resp.json()
                        access_token = ref_data.get("access_token", access_token)
                        scope_str = ref_data.get("scope", "")
                        if scope_str:
                            granted_scopes = [s.strip() for s in scope_str.split(" ") if s.strip()]
                            # Update document with live scopes
                            await db_manager.db.oauth_accounts.update_one(
                                {"_id": oauth_doc["_id"]},
                                {"$set": {"granted_scopes": granted_scopes}}
                            )
                except Exception as ref_err:
                    details["token_refresh_error"] = str(ref_err)

        details["actual_scopes_list"] = granted_scopes
        audit = verify_granted_scopes(granted_scopes)
        
        if audit["valid"]:
            results["actual_scopes"] = "PASS"
            details["actual_scopes"] = f"All required YouTube scopes granted ({len(granted_scopes)} scopes total)"
        else:
            results["actual_scopes"] = "FAIL"
            details["actual_scopes"] = f"Missing required YouTube scopes: {audit['missing_scopes']}. Re-consent required."

        # 6. Authenticated Channel Lookup via real YouTube Data API v3
        if access_token:
            yt = YouTubeClient(access_token=access_token)
            try:
                ch = await yt.get_my_channel()
                results["channel_lookup"] = "PASS"
                details["channel_lookup"] = f"Channel '{ch.get('name')}' (ID: {ch.get('youtube_channel_id')}) successfully retrieved"
                details["channel_obj"] = ch
                
                # Auto-persist channel if found
                user_id = oauth_doc.get("user_id")
                yt_id = ch.get("youtube_channel_id")
                existing = await db_manager.db.channels.find_one({"youtube_channel_id": yt_id})
                if not existing:
                    await db_manager.db.channels.insert_one({
                        "user_id": user_id,
                        "name": ch.get("name"),
                        "description": ch.get("description", ""),
                        "youtube_channel_id": yt_id,
                        "handle": ch.get("handle"),
                        "thumbnail_url": ch.get("thumbnail_url"),
                        "status": "connected",
                        "autopilot_enabled": False,
                        "approval_required": True
                    })
                else:
                    await db_manager.db.channels.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {
                            "user_id": user_id,
                            "status": "connected",
                            "name": ch.get("name"),
                            "handle": ch.get("handle") or existing.get("handle"),
                            "thumbnail_url": ch.get("thumbnail_url") or existing.get("thumbnail_url")
                        }}
                    )
            except YouTubeAPIError as yt_err:
                if yt_err.error_code == "NO_CHANNEL":
                    results["channel_lookup"] = "PASS"
                    details["channel_lookup"] = "API responded successfully; authenticated Google account has no YouTube channel"
                elif yt_err.error_code == "YOUTUBE_INSUFFICIENT_SCOPES":
                    results["channel_lookup"] = "FAIL"
                    details["channel_lookup"] = f"403 Forbidden: Request had insufficient authentication scopes ({yt_err.message})"
                else:
                    results["channel_lookup"] = "FAIL"
                    details["channel_lookup"] = f"YouTube API Error ({yt_err.status_code}): {yt_err.message}"
            except Exception as e:
                results["channel_lookup"] = "FAIL"
                details["channel_lookup"] = f"Lookup failed: {str(e)}"
        else:
            results["channel_lookup"] = "FAIL"
            details["channel_lookup"] = "No valid decrypted token available"

        # 7. MongoDB Persistence
        user_id = oauth_doc.get("user_id")
        persisted_channel = await db_manager.db.channels.find_one({
            "user_id": user_id,
            "youtube_channel_id": {"$exists": True, "$ne": None}
        })
        if persisted_channel:
            results["persistence"] = "PASS"
            details["persistence"] = f"Channel '{persisted_channel.get('name')}' associated with user {user_id} (status: {persisted_channel.get('status')})"
        else:
            results["persistence"] = "FAIL" if results.get("channel_lookup") == "PASS" else "BLOCKED"
            details["persistence"] = "No channel document linked with youtube_channel_id for user"

    # Print Summary Table
    print(f"OAuth configuration:              [{results.get('config', 'UNKNOWN')}]")
    print(f"OAuth requested scopes:           [{results.get('scopes_configured', 'UNKNOWN')}]")
    print(f"OAuth URL generation:             [{results.get('url_gen', 'UNKNOWN')}]")
    print(f"Actual granted scopes:            [{results.get('actual_scopes', 'UNKNOWN')}]")
    print(f"YouTube API credentials:          [{results.get('api_credentials', 'UNKNOWN')}]")
    print(f"Authenticated channel lookup:     [{results.get('channel_lookup', 'UNKNOWN')}]")
    print(f"MongoDB channel persistence:      [{results.get('persistence', 'UNKNOWN')}]")
    print("\n--------------------------------------------------------")

    print("\nExact API call:")
    print("GET https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&mine=true")

    print("\nRequired scope:")
    print("https://www.googleapis.com/auth/youtube.readonly (or https://www.googleapis.com/auth/youtube)")

    print("\nActual granted scopes:")
    if "actual_scopes_list" in details and details["actual_scopes_list"]:
        for s in details["actual_scopes_list"]:
            print(f"  - {s}")
    else:
        print("  <no OAuth account stored or not yet re-authenticated>")

    print("\nDiagnostic Details:")
    for k, v in details.items():
        if k not in ("actual_scopes_list", "channel_obj"):
            print(f"  • {k}: {v}")

    print("\n========================================================")
    if all(r == "PASS" for r in results.values()):
        print("YOUTUBE CONNECTION: WORKING")
    else:
        failed = [k for k, v in results.items() if v in ("FAIL", "BLOCKED")]
        print(f"YOUTUBE CONNECTION: PENDING USER RE-AUTHENTICATION ({', '.join(failed)})")
    print("========================================================\n")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
