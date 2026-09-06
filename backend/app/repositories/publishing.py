from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from bson import ObjectId
from datetime import datetime, timezone

class PublishingRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "publishing_jobs")

    async def find_pending(self, user_id: str) -> list[dict]:
        return await self.find_many({"user_id": user_id, "status": "pending"})

    async def mark_complete(self, id: str, user_id: str, result: dict) -> bool:
        res = await self.collection.update_one(
            {"_id": ObjectId(id), "user_id": user_id},
            {
                "$set": {
                    "status": "completed",
                    "result": result,
                    "completed_at": datetime.now(timezone.utc)
                }
            }
        )
        return res.modified_count > 0

    async def mark_failed(self, id: str, user_id: str, error: str) -> bool:
        res = await self.collection.update_one(
            {"_id": ObjectId(id), "user_id": user_id},
            {
                "$set": {
                    "status": "failed",
                    "error": error,
                    "failed_at": datetime.now(timezone.utc)
                }
            }
        )
        return res.modified_count > 0
