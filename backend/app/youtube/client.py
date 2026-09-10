import httpx
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timezone, timedelta
from loguru import logger

class YouTubeAPIError(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "YOUTUBE_API_ERROR", retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.retryable = retryable

class YouTubeClient:
    """Production client for YouTube Data API v3 and YouTube Analytics API v2.
    Zero-Mock Policy: Never fabricates metrics, upload IDs, or channel details.
    Includes automated token refresh for expiring Google OAuth tokens.
    """
    
    def __init__(
        self,
        access_token: str = "",
        refresh_token: str = "",
        client_id: str = "",
        client_secret: str = "",
        token_refreshed_callback: Optional[Callable[[str, Optional[int]], Awaitable[None]]] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_refreshed_callback = token_refreshed_callback
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.upload_url = "https://www.googleapis.com/upload/youtube/v3/videos"

    def _parse_error(self, response: httpx.Response) -> YouTubeAPIError:
        status_code = response.status_code
        try:
            data = response.json()
            error_details = data.get("error", {})
            errors_list = error_details.get("errors", [])
            reason = errors_list[0].get("reason", "") if errors_list else ""
            raw_msg = error_details.get("message", response.text)
        except Exception:
            reason = ""
            raw_msg = response.text

        if status_code == 401:
            return YouTubeAPIError(
                message="YouTube authorization expired or invalid. Please reconnect your YouTube channel via Google OAuth.",
                status_code=401,
                error_code="YOUTUBE_AUTH_EXPIRED",
                retryable=False
            )
        elif status_code == 403 and ("quota" in reason.lower() or "quota" in raw_msg.lower()):
            return YouTubeAPIError(
                message="YouTube API daily upload quota exceeded. Quota resets at midnight Pacific Time.",
                status_code=403,
                error_code="YOUTUBE_QUOTA_EXCEEDED",
                retryable=False
            )
        elif status_code == 403 and ("insufficient" in raw_msg.lower() or "scope" in raw_msg.lower() or "insufficientpermissions" in reason.lower()):
            return YouTubeAPIError(
                message="YouTube permissions are incomplete. Missing required scope: https://www.googleapis.com/auth/youtube.readonly. Please reconnect your YouTube account.",
                status_code=403,
                error_code="YOUTUBE_INSUFFICIENT_SCOPES",
                retryable=False
            )
        elif status_code == 403:
            return YouTubeAPIError(
                message=f"YouTube permission denied: {raw_msg}",
                status_code=403,
                error_code="YOUTUBE_PERMISSION_DENIED",
                retryable=False
            )
        elif status_code == 404:
            return YouTubeAPIError(
                message="YouTube channel or requested resource not found.",
                status_code=404,
                error_code="YOUTUBE_NOT_FOUND",
                retryable=False
            )
        elif status_code >= 500:
            return YouTubeAPIError(
                message=f"YouTube server error ({status_code}): {raw_msg}",
                status_code=status_code,
                error_code="YOUTUBE_SERVER_ERROR",
                retryable=True
            )
        else:
            return YouTubeAPIError(
                message=f"YouTube API request failed ({status_code}): {raw_msg}",
                status_code=status_code,
                error_code="YOUTUBE_API_ERROR",
                retryable=False
            )

    async def refresh_access_token(self) -> str:
        """Refresh Google OAuth access token using refresh_token."""
        if not self.refresh_token:
            raise YouTubeAPIError(
                message="Cannot refresh YouTube token: no refresh token available. Reconnection required.",
                status_code=401,
                error_code="YOUTUBE_REFRESH_TOKEN_MISSING",
                retryable=False
            )

        from backend.app.config import get_settings
        settings = get_settings()
        client_id = self.client_id or settings.GOOGLE_CLIENT_ID
        client_secret = self.client_secret or settings.GOOGLE_CLIENT_SECRET

        if not client_id or not client_secret:
            raise YouTubeAPIError(
                message="Google OAuth Client ID/Secret not configured on server.",
                status_code=500,
                error_code="GOOGLE_AUTH_UNCONFIGURED",
                retryable=False
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": self.refresh_token,
                        "grant_type": "refresh_token"
                    }
                )
            except Exception as e:
                logger.error(f"Network error refreshing YouTube token: {e}")
                raise YouTubeAPIError(
                    message=f"Network error contacting Google OAuth token service: {e}",
                    status_code=502,
                    error_code="TOKEN_REFRESH_NETWORK_ERROR",
                    retryable=True
                )

        if resp.status_code != 200:
            logger.error(f"Failed to refresh YouTube token ({resp.status_code}): {resp.text}")
            raise YouTubeAPIError(
                message="Google OAuth refresh token expired or revoked. Please reconnect YouTube.",
                status_code=401,
                error_code="YOUTUBE_REAUTH_REQUIRED",
                retryable=False
            )

        data = resp.json()
        new_access_token = data.get("access_token")
        if not new_access_token:
            raise YouTubeAPIError(
                message="Token refresh response did not contain access_token",
                status_code=500,
                error_code="INVALID_REFRESH_RESPONSE"
            )

        self.access_token = new_access_token
        expires_in = data.get("expires_in", 3600)
        logger.info("Successfully refreshed YouTube access token.")

        if self.token_refreshed_callback:
            try:
                await self.token_refreshed_callback(new_access_token, expires_in)
            except Exception as cb_err:
                logger.warning(f"Error executing token_refreshed_callback: {cb_err}")

        return new_access_token

    async def _request_with_auto_refresh(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0
    ) -> httpx.Response:
        """Perform HTTP request with automatic token refresh on 401."""
        if not self.access_token:
            if self.refresh_token:
                await self.refresh_access_token()
            else:
                raise YouTubeAPIError(
                    message="YouTube OAuth access token is required. Please connect your YouTube channel.",
                    status_code=401,
                    error_code="YOUTUBE_AUTH_REQUIRED"
                )

        req_headers = headers.copy() if headers else {}
        req_headers["Authorization"] = f"Bearer {self.access_token}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(method, url, headers=req_headers, params=params, json=json_data)
            if resp.status_code == 401 and self.refresh_token:
                logger.info("Access token expired during YouTube API call. Attempting refresh...")
                await self.refresh_access_token()
                req_headers["Authorization"] = f"Bearer {self.access_token}"
                resp = await client.request(method, url, headers=req_headers, params=params, json=json_data)

            return resp

    async def get_my_channel(self) -> Dict[str, Any]:
        """Fetch authenticated user's YouTube channel metadata.
        Requires https://www.googleapis.com/auth/youtube.readonly or https://www.googleapis.com/auth/youtube
        """
        params = {"part": "snippet,statistics", "mine": "true"}
        resp = await self._request_with_auto_refresh("GET", f"{self.base_url}/channels", params=params, timeout=15.0)

        if resp.status_code != 200:
            raise self._parse_error(resp)
        items = resp.json().get("items", [])
        if not items:
            raise YouTubeAPIError("No YouTube channel found for this Google account.", status_code=404, error_code="NO_CHANNEL")

        ch = items[0]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        thumb = (
            snippet.get("thumbnails", {}).get("high", {}).get("url")
            or snippet.get("thumbnails", {}).get("default", {}).get("url")
        )
        return {
            "id": ch.get("id"),
            "youtube_channel_id": ch.get("id"),
            "title": snippet.get("title"),
            "name": snippet.get("title"),
            "customUrl": snippet.get("customUrl"),
            "handle": snippet.get("customUrl"),
            "description": snippet.get("description", ""),
            "thumbnail_url": thumb,
            "subscriber_count": int(stats.get("subscriberCount", 0)),
            "subscriberCount": int(stats.get("subscriberCount", 0)),
            "video_count": int(stats.get("videoCount", 0)),
            "videoCount": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "viewCount": int(stats.get("viewCount", 0)),
        }

    async def upload_video(self, file_path: str, title: str, description: str = "", tags: list[str] = None, privacy_status: str = "private") -> Dict[str, Any]:
        """Upload video file to YouTube Data API v3 using resumable upload protocol."""
        if not self.access_token:
            if self.refresh_token:
                await self.refresh_access_token()
            else:
                raise YouTubeAPIError(
                    message="YouTube OAuth access token is required to upload videos. Please connect your YouTube channel.",
                    status_code=401,
                    error_code="YOUTUBE_AUTH_REQUIRED"
                )

        import os
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError("Cannot upload an empty video file.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        }

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "28"  # Science & Technology
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: Initiate Resumable Upload Session
            init_url = f"{self.upload_url}?uploadType=resumable&part=snippet,status"
            init_resp = await client.post(init_url, headers=headers, json=body)
            if init_resp.status_code == 401 and self.refresh_token:
                logger.info("Access token expired during upload initiation. Refreshing...")
                await self.refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                init_resp = await client.post(init_url, headers=headers, json=body)

            if init_resp.status_code != 200:
                raise self._parse_error(init_resp)

            upload_location = init_resp.headers.get("Location")
            if not upload_location:
                raise YouTubeAPIError(
                    "YouTube upload initiation did not return a valid upload location URI.",
                    status_code=500,
                    error_code="UPLOAD_LOCATION_MISSING"
                )

            # Step 2: Stream Video Content
            with open(file_path, "rb") as f:
                upload_headers = {
                    "Content-Length": str(file_size),
                    "Content-Type": "video/mp4",
                }
                upload_resp = await client.put(
                    upload_location,
                    headers=upload_headers,
                    content=f.read(),
                    timeout=180.0
                )

            if upload_resp.status_code not in (200, 201):
                raise self._parse_error(upload_resp)

            uploaded_data = upload_resp.json()
            yt_id = uploaded_data.get("id")
            return {
                "youtube_video_id": yt_id,
                "status": "published",
                "privacy_status": privacy_status,
                "url": f"https://youtube.com/watch?v={yt_id}"
            }

    async def set_thumbnail(self, video_id: str, image_path: str) -> bool:
        """Upload custom thumbnail for a published video to YouTube Data API v3."""
        import os
        if not self.access_token:
            if self.refresh_token:
                await self.refresh_access_token()
            else:
                return False

        if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
            return False

        url = f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "image/jpeg"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(image_path, "rb") as f:
                content = f.read()
                resp = await client.post(url, headers=headers, content=content)
                if resp.status_code == 401 and self.refresh_token:
                    await self.refresh_access_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    resp = await client.post(url, headers=headers, content=content)
                return resp.status_code in (200, 201)


    async def get_channel_reports(
        self,
        channel_id: str = "MINE",
        start_date: str = "2024-01-01",
        end_date: str = "2024-12-31",
        metrics: list[str] = None
    ) -> Dict[str, Any]:
        """Fetch real channel metrics from YouTube Analytics API v2."""
        if not metrics:
            metrics = ["views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained", "likes", "comments", "shares"]

        metrics_str = ",".join(metrics)
        target_id = f"channel=={channel_id}" if channel_id and channel_id != "MINE" else "channel==MINE"

        params = {
            "ids": target_id,
            "startDate": start_date,
            "endDate": end_date,
            "metrics": metrics_str,
            "dimensions": "day",
            "sort": "day"
        }

        analytics_url = "https://youtubeanalytics.googleapis.com/v2/reports"
        resp = await self._request_with_auto_refresh("GET", analytics_url, params=params, timeout=30.0)
        if resp.status_code != 200:
            raise self._parse_error(resp)
        return resp.json()

async def get_youtube_client_for_user(user_id: str, db) -> YouTubeClient:
    """Factory creating a YouTubeClient with automated decryption and persistent token refresh.
    Zero-Mock: Uses real stored credentials and persists refreshed tokens to MongoDB.
    """
    oauth_doc = await db.oauth_accounts.find_one({"user_id": user_id, "provider": "google"})
    if not oauth_doc:
        raise YouTubeAPIError(
            message="No Google OAuth account connected for this user. Please connect YouTube.",
            status_code=401,
            error_code="YOUTUBE_NOT_CONNECTED"
        )

    from backend.app.config import get_settings
    settings = get_settings()
    fernet = settings.get_fernet()

    access_token = ""
    refresh_token = ""

    if oauth_doc.get("access_token_encrypted"):
        try:
            access_token = fernet.decrypt(oauth_doc["access_token_encrypted"].encode()).decode()
        except Exception as e:
            logger.warning(f"Could not decrypt stored access token for user {user_id}: {e}")

    if oauth_doc.get("refresh_token_encrypted"):
        try:
            refresh_token = fernet.decrypt(oauth_doc["refresh_token_encrypted"].encode()).decode()
        except Exception as e:
            logger.warning(f"Could not decrypt stored refresh token for user {user_id}: {e}")

    if not access_token and not refresh_token:
        raise YouTubeAPIError(
            message="Valid OAuth tokens not found for user. Please reconnect YouTube.",
            status_code=401,
            error_code="YOUTUBE_TOKENS_MISSING"
        )

    async def on_token_refreshed(new_access_token: str, expires_in: Optional[int]):
        encrypted_new = fernet.encrypt(new_access_token.encode()).decode()
        update_data = {
            "access_token_encrypted": encrypted_new,
            "updated_at": datetime.now(timezone.utc)
        }
        if expires_in:
            update_data["token_expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        await db.oauth_accounts.update_one(
            {"_id": oauth_doc["_id"]},
            {"$set": update_data}
        )
        logger.info(f"Persisted refreshed OAuth access token for user {user_id} to MongoDB.")

    return YouTubeClient(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_refreshed_callback=on_token_refreshed
    )

