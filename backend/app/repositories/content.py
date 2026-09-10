from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from bson import ObjectId

class ContentIdeaRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "content_ideas")

    async def find_by_channel(self, user_id: str, channel_id: str = None, status: str = None, skip: int = 0, limit: int = 50) -> list[dict]:
        query = {"user_id": user_id}
        if channel_id:
            query["channel_id"] = channel_id
        if status:
            query["status"] = status
        return await self.find_many(query, skip=skip, limit=limit)

    async def update_status(self, id: str, user_id: str, status: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(id), "user_id": user_id},
            {"$set": {"status": status}}
        )
        return result.modified_count > 0


class ScriptRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "scripts")

    async def find_by_channel(self, user_id: str, channel_id: str) -> list[dict]:
        return await self.find_many({"user_id": user_id, "channel_id": channel_id})

    async def find_by_content_idea(self, content_idea_id: str) -> dict | None:
        return await self.collection.find_one({"content_idea_id": content_idea_id})
