from loguru import logger
from backend.app.workers.base import BaseWorker
from backend.app.ai.gateway import AIGateway
from backend.app.services.analytics_service import AnalyticsService

class AnalyticsWorker(BaseWorker):
    job_type = "analytics_sync"
    poll_interval = 10.0
    
    async def process(self, job: dict):
        job_id = str(job["_id"])
        user_id = job["user_id"]
        channel_id = job.get("channel_id")
        payload = job.get("payload", {})
        
        await self.update_progress(job_id, 10, stage="fetching_stats")
        
        ai = AIGateway(base_url=self.settings.OLLAMA_BASE_URL, model=self.settings.OLLAMA_MODEL) if self.settings else AIGateway()
        analytics_service = AnalyticsService(self.db, ai)
        
        await self.update_progress(job_id, 40, stage="creating_snapshot")
        
        # Ingest snapshot payload if provided
        snapshot_data = payload.get("snapshot") or {
            "channel_id": channel_id,
            "views": payload.get("views", 100),
            "likes": payload.get("likes", 10),
            "comments": payload.get("comments", 2),
            "shares": payload.get("shares", 1),
            "watch_time_hours": payload.get("watch_time_hours", 2.5),
            "subscribers_gained": payload.get("subscribers_gained", 5),
            "ctr": payload.get("ctr", 7.2),
            "avg_view_duration": payload.get("avg_view_duration", 38.0),
            "period": "daily"
        }
        
        created = await analytics_service.create_snapshot(user_id, snapshot_data)
        
        await self.update_progress(job_id, 100, stage="completed")
        await self.job_repo.update_progress(job_id, 100, result=created, status="completed")
        logger.info(f"AnalyticsWorker synced snapshot for channel {channel_id}")
