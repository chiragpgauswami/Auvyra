"""
Background Scheduler Worker (Phase 20).
Runs the lightweight scheduler loop:
- Reclaims expired leases
- Replenishes 7-day bounded queue
- Claims due slots and dispatches to jobs collection
Does NOT perform heavy AI or video rendering inside this loop.
"""

import asyncio
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.workers.base import BaseWorker
from backend.app.services.scheduler_service import SchedulerService

class SchedulerWorker:
    def __init__(self, db: AsyncIOMotorDatabase, settings=None, poll_interval: float = 10.0):
        self.db = db
        self.settings = settings
        self.poll_interval = poll_interval
        self.service = SchedulerService(db)
        self._running = False

    async def run(self):
        self._running = True
        logger.info(f"SchedulerWorker started (poll_interval={self.poll_interval}s)")
        while self._running:
            try:
                res = await self.service.tick()
                if res.get("reclaimed_leases") or res.get("replenished_slots") or res.get("claimed_slots"):
                    logger.info(f"Scheduler tick: {res}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SchedulerWorker tick: {e}")

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

        logger.info("SchedulerWorker stopped")

    def stop(self):
        self._running = False

