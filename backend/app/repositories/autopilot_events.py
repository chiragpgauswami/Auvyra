"""
Repository for append-only Autopilot event telemetry.
Maintains an immutable historical record of all stage progressions, warnings, and errors.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository

class AutopilotEventsRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "autopilot_events")

    async def record_event(
        self,
        channel_id: str,
        user_id: str,
        queue_item_id: str,
        stage: str,
        status: str,  # started, progress, completed, failed, retrying
        progress: int = 0,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None,
        video_id: Optional[str] = None
    ) -> str:
        """Appends a new immutable telemetry event. Never updates or mutates existing events."""
        event_doc = {
            "channel_id": channel_id,
            "user_id": user_id,
            "queue_item_id": queue_item_id,
            "video_id": video_id,
            "stage": stage,
            "status": status,
            "progress": progress,
            "message": message,
            "metadata": metadata or {},
            "error": error,
            "timestamp": datetime.now(timezone.utc)
        }
        res = await self.collection.insert_one(event_doc)
        return str(res.inserted_id)

    async def find_by_channel(
        self,
        channel_id: str,
        user_id: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieves append-only events for a channel in reverse chronological order."""
        cursor = self.collection.find(
            {"channel_id": channel_id, "user_id": user_id}
        ).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_queue_item(
        self,
        queue_item_id: str,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """Retrieves chronological milestones for a specific queue item."""
        cursor = self.collection.find(
            {"queue_item_id": queue_item_id, "user_id": user_id}
        ).sort("timestamp", 1)
        return await cursor.to_list(length=200)

    get_channel_events = find_by_channel

