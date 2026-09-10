import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from loguru import logger
from backend.app.repositories.publishing import PublishingRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.repositories.users import OAuthAccountRepository
from backend.app.youtube.client import YouTubeClient, YouTubeAPIError, get_youtube_client_for_user
from backend.app.config import get_settings
from backend.app.utils.serializers import serialize_doc, serialize_docs

class PublishingService:
    def __init__(self, db):
        self.db = db
        self.pub_repo = PublishingRepository(db)
        self.video_repo = VideoRepository(db)
        self.oauth_repo = OAuthAccountRepository(db)
        self.settings = get_settings()
    
    async def create_publishing_job(
        self,
        user_id: str,
        video_id: str,
        platform: str = "youtube",
        metadata: dict = None,
        scheduled_at: Optional[datetime] = None
    ) -> dict:
        video = await self.video_repo.find_by_id(video_id, user_id=user_id)
        if not video:
            raise ValueError(f"Video {video_id} not found or access denied")

        status_val = "scheduled" if scheduled_at and scheduled_at > datetime.now(timezone.utc) else "pending"
            
        job_data = {
            "user_id": user_id,
            "video_id": video_id,
            "channel_id": video.get("channel_id"),
            "platform": platform,
            "metadata": metadata or {},
            "scheduled_at": scheduled_at,
            "status": status_val,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        job_id = await self.pub_repo.insert_one(job_data)
        job_data["id"] = job_id
        return serialize_doc(job_data)
    
    async def list_publishing_jobs(self, user_id: str) -> List[dict]:
        jobs = await self.pub_repo.find_many({"user_id": user_id})
        return serialize_docs(jobs)
        
    async def get_publishing_status(self, user_id: str, job_id: str) -> Optional[dict]:
        job = await self.pub_repo.find_by_id(job_id, user_id=user_id)
        return serialize_doc(job)

    async def get_publishing_calendar(self, user_id: str) -> List[dict]:
        """Returns consolidated calendar schedule of pending, scheduled, and published content."""
        jobs = await self.pub_repo.find_many({"user_id": user_id})
        videos = await self.video_repo.find_many({"user_id": user_id})
        video_map = {str(v.get("_id")): v for v in videos}

        events = []
        for j in jobs:
            v_id = str(j.get("video_id"))
            vid = video_map.get(v_id, {})
            title = j.get("metadata", {}).get("title") or vid.get("title", "Scheduled Video")
            dt = j.get("scheduled_at") or j.get("created_at")
            events.append({
                "job_id": str(j.get("_id")),
                "video_id": v_id,
                "title": title,
                "status": j.get("status", "pending"),
                "date": dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                "platform": j.get("platform", "youtube"),
                "thumbnail_url": vid.get("thumbnail_path") or vid.get("thumbnail_url")
            })

        events.sort(key=lambda x: x.get("date", ""), reverse=True)
        return events

    async def execute_publish(self, user_id: str, job_id: str, is_mock: bool = False) -> dict:
        """Executes actual or mock-tested publishing to YouTube."""
        job = await self.pub_repo.find_by_id(job_id, user_id=user_id)
        if not job:
            raise ValueError(f"Publishing job {job_id} not found")

        video_id = job.get("video_id")
        video = await self.video_repo.find_by_id(video_id, user_id=user_id)
        if not video:
            raise ValueError(f"Video {video_id} not found")

        metadata = job.get("metadata", {})
        title = metadata.get("title") or video.get("title", "Untitled Video")
        description = metadata.get("description") or video.get("description", "")
        tags = metadata.get("tags") or video.get("tags", [])
        privacy = metadata.get("privacy", "private")
        file_path = video.get("file_path", "")

        # Get connected YouTube client for this user with automatic token refresh
        yt_client = await get_youtube_client_for_user(user_id, self.db)
        if not yt_client or (not yt_client.access_token and not yt_client.refresh_token):
            error_msg = "Google OAuth is not configured or YouTube channel is not connected. Connect YouTube via OAuth before publishing."
            logger.error(f"Publishing blocked for job {job_id}: {error_msg}")
            await self.pub_repo.mark_failed(job_id, user_id, error_msg)
            raise YouTubeAPIError(
                message=error_msg,
                status_code=400,
                error_code="GOOGLE_OAUTH_NOT_CONFIGURED"
            )

        if is_mock:
            yt_client.is_mock = True

        try:
            res = await yt_client.upload_video(
                file_path=file_path,
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy
            )
            
            yt_id = res.get("youtube_video_id")

            # Set custom thumbnail if available
            thumb_path = metadata.get("thumbnail_path") or video.get("thumbnail_path")
            if thumb_path and os.path.exists(thumb_path) and yt_id:
                try:
                    await yt_client.set_thumbnail(yt_id, thumb_path)
                    res["thumbnail_uploaded"] = True
                except Exception as te:
                    logger.warning(f"Thumbnail upload failed for {yt_id}: {te}")
                    res["thumbnail_uploaded"] = False

            # Update video record only after successful publish
            now = datetime.now(timezone.utc)
            await self.video_repo.update_one(
                video_id,
                {
                    "status": "published",
                    "youtube_video_id": yt_id,
                    "published_at": now,
                    "youtube_url": res.get("url")
                },
                user_id=user_id
            )
            
            await self.pub_repo.mark_complete(job_id, user_id, res)
            return res
        except YouTubeAPIError as e:
            logger.error(f"YouTube publishing failed for job {job_id}: {e.message}")
            await self.pub_repo.mark_failed(job_id, user_id, e.message)
            raise
