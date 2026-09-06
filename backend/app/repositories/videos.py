from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from bson import ObjectId

class VideoRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "videos")

    async def find_by_channel(self, user_id: str, channel_id: str, status: str = None) -> list[dict]:
        query = {"user_id": user_id, "channel_id": channel_id}
        if status:
            query["status"] = status
        return await self.find_many(query)

    async def find_by_status(self, user_id: str, status: str) -> list[dict]:
        return await self.find_many({"user_id": user_id, "status": status})

    async def update_status(self, id: str, user_id: str, status: str, **extra) -> bool:
        update_doc = {"status": status, **extra}
        result = await self.collection.update_one(
            {"_id": ObjectId(id), "user_id": user_id},
            {"$set": update_doc}
        )
        return result.modified_count > 0


class VideoAssetRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "video_assets")

    async def find_by_video(self, video_id: str) -> list[dict]:
        return await self.find_many({"video_id": video_id})

    async def create_asset(self, asset_data: dict) -> str:
        return await self.insert_one(asset_data)
