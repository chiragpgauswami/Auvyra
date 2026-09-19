import asyncio
import signal
from loguru import logger

from backend.app.workers.video_worker import VideoWorker
from backend.app.workers.research_worker import ResearchWorker
from backend.app.workers.script_worker import ScriptWorker
from backend.app.workers.publishing_worker import PublishingWorker
from backend.app.workers.analytics_worker import AnalyticsWorker
from backend.app.workers.learning_worker import LearningWorker
from backend.app.workers.scheduler_worker import SchedulerWorker
from backend.app.workers.autopilot_worker import AutopilotWorker

async def run_workers(worker_types: list[str] | None = None):
    """Start specified workers (or all) and run until stopped."""
    from backend.app.database import db_manager
    from backend.app.config import get_settings
    
    settings = get_settings()
    await db_manager.connect(settings.MONGODB_URI, settings.MONGODB_DATABASE)
    db = db_manager.get_database()
    
    all_worker_classes = {
        "video_generation": VideoWorker,
        "research": ResearchWorker,
        "script_generation": ScriptWorker,
        "publishing": PublishingWorker,
        "analytics_sync": AnalyticsWorker,
        "learning": LearningWorker,
        "scheduler": SchedulerWorker,
        "autopilot": AutopilotWorker,
    }
    
    types_to_run = worker_types or list(all_worker_classes.keys())
    workers = []
    tasks = []
    
    for worker_type in types_to_run:
        cls = all_worker_classes.get(worker_type)
        if cls:
            worker = cls(db, settings)
            workers.append(worker)
            tasks.append(asyncio.create_task(worker.run()))
            logger.info(f"Started worker: {worker_type}")
    
    logger.info(f"All {len(workers)} workers running. Press Ctrl+C to stop.")
    
    # Handle graceful shutdown
    stop_event = asyncio.Event()
    
    def signal_handler():
        logger.info("Shutdown signal received")
        for worker in workers:
            worker.stop()
        stop_event.set()
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler
    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        pass
    finally:
        await db_manager.disconnect()
        logger.info("All workers stopped")


def main():
    """Entry point for running workers from command line."""
    import argparse
    parser = argparse.ArgumentParser(description="Run Auvyra background workers")
    parser.add_argument(
        "--workers", "-w",
        nargs="*",
        choices=["video_generation", "research", "script_generation", "publishing", "analytics_sync", "learning"],
        help="Specific workers to run (default: all)"
    )
    args = parser.parse_args()
    asyncio.run(run_workers(args.workers))


if __name__ == "__main__":
    main()
