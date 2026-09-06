from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from bson import ObjectId
from datetime import datetime, timezone
from typing import Any

class JobRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "jobs")

    async def enqueue(self, job_type: str, user_id: str, channel_id: str = None, payload: dict = None) -> str:
        if payload is None:
            payload = {}
        data = {
            "type": job_type,
            "user_id": user_id,
            "channel_id": channel_id,
            "payload": payload,
            "status": "queued",
            "progress": 0,
            "attempts": 0,
            "max_attempts": 3
        }
        return await self.insert_one(data)

    async def dequeue(self, job_type: str) -> dict | None:
        """Atomically find one queued job and set to processing."""
        result = await self.collection.find_one_and_update(
            {"type": job_type, "status": "queued"},
            {"$set": {"status": "processing", "started_at": datetime.now(timezone.utc)}},
            sort=[("created_at", 1)],
            return_document=True
        )
        return result

    async def update_progress(self, id: str, progress: int, **extra) -> bool:
        update_doc = {"progress": progress, **extra}
        result = await self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_doc}
        )
        return result.modified_count > 0

    async def mark_complete(self, id: str, result: dict = None) -> bool:
        update_doc = {
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.now(timezone.utc)
        }
        if result is not None:
            update_doc["result"] = result
        res = await self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_doc}
        )
        return res.modified_count > 0

    async def mark_failed(self, id: str, error: str) -> bool:
        res = await self.collection.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "status": "failed",
                    "error": error,
                    "completed_at": datetime.now(timezone.utc)
                }
            }
        )
        return res.modified_count > 0

    async def find_by_user(self, user_id: str, status: str = None, limit: int = 50) -> list[dict]:
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        return await self.find_many(query, limit=limit)

    async def retry_failed(self, id: str) -> bool:
        res = await self.collection.update_one(
            {"_id": ObjectId(id), "status": "failed", "$expr": {"$lt": ["$attempts", "$max_attempts"]}},
            {
                "$set": {"status": "queued", "error": None, "started_at": None, "completed_at": None},
                "$inc": {"attempts": 1}
            }
        )
        return res.modified_count > 0

    async def recover_stale_jobs(self, timeout_minutes: int = 15) -> int:
        """Recover jobs left in 'processing' status after a worker crash or hang."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        res = await self.collection.update_many(
            {
                "status": "processing",
                "started_at": {"$lt": cutoff},
                "$expr": {"$lt": ["$attempts", "$max_attempts"]}
            },
            {
                "$set": {"status": "queued", "started_at": None},
                "$inc": {"attempts": 1}
            }
        )
        return res.modified_count


class NotificationRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "notifications")

    async def find_by_user(self, user_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
        query = {"user_id": user_id}
        if unread_only:
            query["read"] = False
        return await self.find_many(query, limit=limit, sort=[("created_at", -1)])

    async def mark_read(self, id: str, user_id: str) -> bool:
        res = await self.collection.update_one(
            {"_id": ObjectId(id), "user_id": user_id},
            {"$set": {"read": True}}
        )
        return res.modified_count > 0

    async def create_notification(self, user_id: str, type: str, title: str, message: str, data: dict = None) -> str:
        if data is None:
            data = {}
        doc = {
            "user_id": user_id,
            "type": type,
            "title": title,
            "message": message,
            "data": data,
            "read": False
        }
        return await self.insert_one(doc)


class SystemSettingsRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "system_settings")

    async def get_setting(self, key: str) -> Any:
        doc = await self.collection.find_one({"key": key})
        return doc["value"] if doc else None

    async def set_setting(self, key: str, value: Any) -> bool:
        res = await self.collection.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        return res.modified_count > 0 or res.upserted_id is not None
