from backend.app.workers.base import BaseWorker
from backend.app.ai.gateway import AIGateway
from backend.app.services.content_service import ContentService
from loguru import logger

class ScriptWorker(BaseWorker):
    job_type = "script_generation"
    poll_interval = 3.0
    
    async def process(self, job: dict):
        job_id = str(job["_id"])
        user_id = job["user_id"]
        channel_id = job.get("channel_id")
        payload = job.get("payload", {})
        
        topic = payload.get("topic", "")
        duration = payload.get("duration", 45)
        channel_context = payload.get("channel_context")
        
        await self.update_progress(job_id, 15, stage="drafting")
        
        ai = AIGateway(base_url=self.settings.OLLAMA_BASE_URL, model=self.settings.OLLAMA_MODEL) if self.settings else AIGateway()
        content_service = ContentService(self.db, ai)
        
        await self.update_progress(job_id, 50, stage="scoring_hooks")
        result = await content_service.generate_script(user_id, channel_id, topic, duration=duration, channel_context=channel_context)
        
        await self.update_progress(job_id, 100, stage="completed")
        await self.job_repo.update_progress(job_id, 100, result=result, status="completed")
        logger.info(f"ScriptWorker finished script generation for '{topic}'")
