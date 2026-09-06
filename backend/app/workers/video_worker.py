from backend.app.workers.base import BaseWorker
from backend.app.services.video_service import VideoService
from backend.app.storage.local import LocalStorageProvider
from backend.app.ai.gateway import AIGateway
from loguru import logger

class VideoWorker(BaseWorker):
    job_type = "video_generation"
    poll_interval = 2.0
    
    def __init__(self, db, settings=None):
        super().__init__(db, settings)
        storage = LocalStorageProvider(settings.MEDIA_ROOT if settings else "media")
        ai = AIGateway(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL) if settings else AIGateway()
        self.video_service = VideoService(db, storage=storage, ai_gateway=ai)
    
    async def process(self, job: dict):
        job_id = str(job["_id"])
        user_id = job["user_id"]
        payload = job.get("payload", {})
        
        logger.info(f"VideoWorker starting generation for job {job_id} (user {user_id})")
        
        def on_progress(p):
            # Update progress synchronously via task or repo
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.update_progress(job_id, p.percent, stage=p.stage, message=p.message))
            except Exception as e:
                logger.debug(f"Progress update skipped: {e}")
        
        result = await self.video_service.process_video_job(job, progress_callback=on_progress)
        await self.job_repo.update_progress(job_id, 100, result=result, status="completed")
        logger.success(f"VideoWorker completed job {job_id}")
