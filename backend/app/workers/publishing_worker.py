from loguru import logger
from backend.app.workers.base import BaseWorker
from backend.app.services.publishing_service import PublishingService

class PublishingWorker(BaseWorker):
    job_type = "publishing"
    poll_interval = 5.0
    
    async def process(self, job: dict):
        job_id = str(job["_id"])
        user_id = job["user_id"]
        payload = job.get("payload", {})
        video_id = payload.get("video_id")
        platform = payload.get("platform", "youtube")
        metadata = payload.get("metadata", {})
        is_mock = payload.get("is_mock", False)
        
        await self.update_progress(job_id, 10, stage="initializing")
        
        publishing_service = PublishingService(self.db)
        
        # Create publishing job record if not already created
        pub_job = await publishing_service.create_publishing_job(
            user_id=user_id,
            video_id=video_id,
            platform=platform,
            metadata=metadata
        )
        
        await self.update_progress(job_id, 40, stage="uploading")
        
        result = await publishing_service.execute_publish(
            user_id=user_id,
            job_id=pub_job["id"],
            is_mock=is_mock
        )
        
        await self.update_progress(job_id, 100, stage="completed")
        await self.job_repo.update_progress(job_id, 100, result=result, status="completed")
        logger.success(f"PublishingWorker published video {video_id} to {platform}")
