from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from loguru import logger
from backend.app.repositories.publishing import PublishingRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.repositories.users import OAuthAccountRepository
from backend.app.youtube.client import YouTubeClient, YouTubeAPIError
from backend.app.config import get_settings
from backend.app.utils.serializers import serialize_doc, serialize_docs

class PublishingService:
    def __init__(self, db):
        self.pub_repo = PublishingRepository(db)
        self.video_repo = VideoRepository(db)
        self.oauth_repo = OAuthAccountRepository(db)
        self.settings = get_settings()
    
    async def create_publishing_job(self, user_id: str, video_id: str, platform: str = "youtube", metadata: dict = None) -> dict:
        video = await self.video_repo.find_by_id(video_id, user_id=user_id)
        if not video:
            raise ValueError(f"Video {video_id} not found or access denied")
            
        job_data = {
            "user_id": user_id,
            "video_id": video_id,
            "platform": platform,
            "metadata": metadata or {},
            "status": "pending"
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

    async def execute_publish(self, user_id: str, job_id: str, is_mock: bool = False) -> dict:
        """Executes actual or mocked publishing to YouTube."""
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

        # Fetch decrypted OAuth token for YouTube
        oauth_account = await self.oauth_repo.find_by_provider(user_id, "google")
        token = ""
        if oauth_account and oauth_account.get("access_token_encrypted"):
            fernet = self.settings.get_fernet()
            try:
                token = fernet.decrypt(oauth_account["access_token_encrypted"].encode()).decode()
            except Exception as e:
                logger.warning(f"Could not decrypt OAuth access token: {e}")

        # If no real token available or mock requested, run mock client
        client_is_mock = is_mock or (not token)
        yt_client = YouTubeClient(access_token=token, is_mock=client_is_mock)
        
        try:
            res = await yt_client.upload_video(
                file_path=file_path,
                title=title,
                description=description,
                tags=tags,
                privacy_status=privacy
            )
            
            # Update video record only after successful publish
            now = datetime.now(timezone.utc)
            await self.video_repo.update_one(
                video_id,
                {
                    "status": "published",
                    "youtube_video_id": res.get("youtube_video_id"),
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