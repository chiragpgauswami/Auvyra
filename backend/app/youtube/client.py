import httpx
from typing import Dict, Any, Optional
from loguru import logger

class YouTubeAPIError(Exception):
    def __init__(self, message: str, status_code: int = 400, error_code: str = "YOUTUBE_API_ERROR", retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.retryable = retryable

class YouTubeClient:
    """Production client for YouTube Data API v3 with robust error parsing and quota handling."""
    
    def __init__(self, access_token: str = "", is_mock: bool = False):
        self.access_token = access_token
        self.is_mock = is_mock
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
                message="YouTube authorization expired or invalid. Please reconnect your YouTube channel.",
                status_code=401,
                error_code="YOUTUBE_AUTH_EXPIRED",
                retryable=False
            )
        elif status_code == 403 and ("quota" in reason.lower() or "quota" in raw_msg.lower()):
            return YouTubeAPIError(
                message="YouTube API daily upload quota exceeded. Please wait for quota reset at midnight Pacific Time.",
                status_code=403,
                error_code="YOUTUBE_QUOTA_EXCEEDED",
                retryable=False  # Do NOT repeatedly retry quota exhaustion
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
        elif status_code == 429:
            return YouTubeAPIError(
                message="YouTube API rate limit reached. Please retry in a few minutes.",
                status_code=429,
                error_code="YOUTUBE_RATE_LIMIT",
                retryable=True
            )
        elif status_code >= 500:
            return YouTubeAPIError(
                message="YouTube service temporarily unavailable. Please retry later.",
                status_code=status_code,
                error_code="YOUTUBE_SERVER_ERROR",
                retryable=True
            )
        else:
            return YouTubeAPIError(
                message=f"YouTube API error: {raw_msg}",
                status_code=status_code,
                error_code="YOUTUBE_API_ERROR",
                retryable=False
            )

    async def get_my_channel(self) -> Dict[str, Any]:
        """Fetch authenticated user's YouTube channel metadata."""
        if self.is_mock:
            return {
                "id": "UC_MOCK_CHANNEL_123",
                "title": "Mock Automation Channel",
                "customUrl": "@mockautochannel",
                "subscriberCount": 1540,
                "videoCount": 24,
                "is_mock": True
            }

        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"part": "snippet,statistics", "mine": "true"}
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{self.base_url}/channels", headers=headers, params=params)
            if resp.status_code != 200:
                raise self._parse_error(resp)
            items = resp.json().get("items", [])
            if not items:
                raise YouTubeAPIError("No YouTube channel found for this Google account.", status_code=404, error_code="NO_CHANNEL")
            
            ch = items[0]
            snippet = ch.get("snippet", {})
            stats = ch.get("statistics", {})
            return {
                "id": ch.get("id"),
                "title": snippet.get("title"),
                "customUrl": snippet.get("customUrl"),
                "description": snippet.get("description"),
                "subscriberCount": int(stats.get("subscriberCount", 0)),
                "videoCount": int(stats.get("videoCount", 0)),
                "is_mock": False
            }

    async def upload_video(self, file_path: str, title: str, description: str = "", tags: list[str] = None, privacy_status: str = "private") -> Dict[str, Any]:
        """Upload video file to YouTube Data API v3."""
        if self.is_mock:
            logger.info(f"[MOCK YOUTUBE] Uploading {file_path} as title: '{title}'")
            return {
                "youtube_video_id": f"mock_yt_{hash(title) % 1000000}",
                "status": "uploaded",
                "privacy_status": privacy_status,
                "url": f"https://youtube.com/watch?v=mock_yt_{hash(title) % 1000000}",
                "is_mock": True
            }

        # Real YouTube Upload via resumable multipart protocol
        headers = {"Authorization": f"Bearer {self.access_token}"}
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or []
            },
            "status": {
                "privacyStatus": privacy_status
            }
        }
        
        import os
        if not os.path.exists(file_path):
            raise YouTubeAPIError(f"Video file not found at {file_path}", status_code=404, error_code="FILE_NOT_FOUND")

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(file_path, "rb") as vf:
                files = {
                    "snippet": (None, str(body), "application/json"),
                    "file": ("video.mp4", vf, "video/mp4")
                }
                resp = await client.post(
                    f"{self.upload_url}?uploadType=multipart&part=snippet,status",
                    headers=headers,
                    files=files
                )
                
            if resp.status_code not in (200, 201):
                raise self._parse_error(resp)
                
            data = resp.json()
            yt_id = data.get("id")
            return {
                "youtube_video_id": yt_id,
                "status": "published",
                "privacy_status": privacy_status,
                "url": f"https://youtube.com/watch?v={yt_id}",
                "is_mock": False
            }
