from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from datetime import datetime, timezone
from bson import ObjectId

class ChannelRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "channels")

    async def find_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
        return await self.find_many({"user_id": user_id}, skip=skip, limit=limit)

    async def find_by_youtube_id(self, youtube_channel_id: str) -> dict | None:
        return await self.collection.find_one({"youtube_channel_id": youtube_channel_id})

    async def find_by_oauth_account(self, oauth_account_id: str, user_id: str | None = None) -> list[dict]:
        query = {"oauth_account_id": oauth_account_id}
        if user_id:
            query["user_id"] = user_id
        cursor = self.collection.find(query)
        return await cursor.to_list(length=100)

    async def disconnect_channels_for_oauth_account(self, oauth_account_id: str, user_id: str) -> int:
        """Mark channels associated with this OAuth account as disconnected and pause autopilot, preserving historical data."""
        result = await self.collection.update_many(
            {"oauth_account_id": oauth_account_id, "user_id": user_id},
            {
                "$set": {
                    "status": "disconnected",
                    "autopilot_enabled": False,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count


class ChannelMemoryRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "channel_memory")

    async def get_memory(self, channel_id: str) -> dict | None:
        return await self.collection.find_one({"channel_id": channel_id})

    async def update_memory(self, channel_id: str, memory_data: dict) -> bool:
        memory_data["last_updated"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"channel_id": channel_id},
            {"$set": memory_data},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def add_insight(self, channel_id: str, insight: dict) -> bool:
        # Insight must include source, confidence, supporting_metrics, created_at
        insight["created_at"] = insight.get("created_at", datetime.now(timezone.utc))
        result = await self.collection.update_one(
            {"channel_id": channel_id},
            {
                "$push": {"strategy_insights": insight},
                "$set": {"last_updated": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None
