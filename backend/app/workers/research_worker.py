from backend.app.workers.base import BaseWorker
from backend.app.ai.gateway import AIGateway
from backend.app.services.research_service import ResearchService
from loguru import logger

class ResearchWorker(BaseWorker):
    job_type = "research"
    poll_interval = 3.0
    
    async def process(self, job: dict):
        job_id = str(job["_id"])
        user_id = job["user_id"]
        channel_id = job.get("channel_id")
        payload = job.get("payload", {})
        topic = payload.get("topic", "Trending AI Topics")
        channel_context = payload.get("channel_context")
        
        await self.update_progress(job_id, 10, stage="initializing")
        
        ai = AIGateway(base_url=self.settings.OLLAMA_BASE_URL, model=self.settings.OLLAMA_MODEL) if self.settings else AIGateway()
        research_service = ResearchService(self.db, ai)
        
        await self.update_progress(job_id, 40, stage="researching")
        result = await research_service.create_research(user_id, channel_id, topic, channel_context=channel_context)
        
        await self.update_progress(job_id, 100, stage="completed")
        await self.job_repo.update_progress(job_id, 100, result=result, status="completed")
        logger.info(f"ResearchWorker finished report for topic '{topic}'")
