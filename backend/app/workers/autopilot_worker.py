"""
Autopilot Production Worker (Phase 20).
Picks up 'autopilot_orchestration' jobs and executes granular, idempotent pipeline stages.
"""

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.workers.base import BaseWorker
from backend.app.services.autopilot_service import AutopilotService
from backend.app.models.job import JobType

class AutopilotWorker(BaseWorker):
    job_type = JobType.autopilot_orchestration.value
    poll_interval = 3.0

    def __init__(self, db: AsyncIOMotorDatabase, settings=None):
        super().__init__(db, settings)
        self.autopilot_service = AutopilotService(db)

    async def process(self, job: dict):
        job_id = str(job["_id"])
        payload = job.get("payload", {})
        queue_item_id = payload.get("queue_item_id")
        worker_id = payload.get("worker_id", f"worker_{job_id}")

        if not queue_item_id:
            raise ValueError("Job payload missing 'queue_item_id'")

        logger.info(f"AutopilotWorker processing queue slot: {queue_item_id} (job={job_id})")

        # Execute granular pipeline stages
        result = await self.autopilot_service.execute_queue_item(
            queue_item_id=queue_item_id,
            worker_id=worker_id
        )

        await self.update_progress(job_id, 100, result=result)
        logger.info(f"AutopilotWorker successfully completed queue slot: {queue_item_id}")

