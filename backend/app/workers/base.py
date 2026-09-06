import asyncio
from datetime import datetime, timezone
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.repositories.jobs import JobRepository

class BaseWorker:
    """Base worker that polls MongoDB jobs collection.
    
    Designed so Redis/Arq/Celery can be introduced later if scaling requires it.
    Currently uses MongoDB-based atomic polling with configurable interval.
    """
    
    job_type: str = ""  # Override in subclass
    poll_interval: float = 3.0  # seconds between polls
    
    def __init__(self, db: AsyncIOMotorDatabase, settings=None):
        self.db = db
        self.settings = settings
        self.job_repo = JobRepository(db)
        self._running = False
        self._loop_count = 0
    
    async def run(self):
        """Main worker loop. Poll for jobs, process them, and recover stale jobs."""
        self._running = True
        logger.info(f"Worker started: {self.__class__.__name__} (type={self.job_type})")
        while self._running:
            try:
                self._loop_count += 1
                # Periodically recover stale jobs that crashed or timed out (every ~10 loops)
                if self._loop_count % 10 == 0:
                    recovered = await self.job_repo.recover_stale_jobs(timeout_minutes=15)
                    if recovered > 0:
                        logger.info(f"[{self.job_type}] Recovered {recovered} stale jobs back to queued.")

                job = await self.job_repo.dequeue(self.job_type)
                if job:
                    job_id = str(job["_id"])
                    logger.info(f"Processing job: {job_id} (type={self.job_type})")
                    try:
                        await self.process(job)
                        await self.job_repo.mark_complete(job_id)
                        logger.info(f"Job completed: {job_id}")
                    except Exception as e:
                        logger.error(f"Job failed: {job_id}, error: {e}")
                        attempts = job.get("attempts", 0) + 1
                        max_attempts = job.get("max_attempts", 3)
                        if attempts < max_attempts:
                            await self.job_repo.retry_failed(job_id)
                            logger.info(f"Job queued for retry: {job_id} (attempt {attempts}/{max_attempts})")
                        else:
                            await self.job_repo.mark_failed(job_id, str(e))
                            logger.error(f"Job permanently failed: {job_id}")
                else:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info(f"Worker stopping: {self.__class__.__name__}")
                break
            except Exception as e:
                logger.error(f"Worker error in {self.__class__.__name__}: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def process(self, job: dict):
        """Process a single job. Override in subclass."""
        raise NotImplementedError
    
    async def update_progress(self, job_id: str, progress: int, **extra):
        """Update job progress (0-100)."""
        await self.job_repo.update_progress(job_id, progress, **extra)
    
    def stop(self):
        self._running = False
