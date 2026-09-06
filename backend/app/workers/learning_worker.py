from loguru import logger
from backend.app.workers.base import BaseWorker
from backend.app.ai.gateway import AIGateway
from backend.app.services.learning_service import LearningService

class LearningWorker(BaseWorker):
    job_type = "learning"
    poll_interval = 10.0
    
    async def process(self, job: dict):
        job_id = str(job["_id"])
        user_id = job["user_id"]
        channel_id = job.get("channel_id")
        
        await self.update_progress(job_id, 10, stage="analyzing_performance")
        
        ai = AIGateway(base_url=self.settings.OLLAMA_BASE_URL, model=self.settings.OLLAMA_MODEL) if self.settings else AIGateway()
        learning_service = LearningService(self.db, ai)
        
        await self.update_progress(job_id, 40, stage="updating_channel_memory")
        result = await learning_service.update_channel_memory(user_id, channel_id)
        
        await self.update_progress(job_id, 100, stage="completed")
        await self.job_repo.update_progress(job_id, 100, result=result, status="completed")
        logger.info(f"LearningWorker updated channel memory for channel {channel_id}")
