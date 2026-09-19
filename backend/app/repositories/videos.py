from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from bson import ObjectId

class VideoRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "videos")

    async def find_by_channel(self, user_id: str, channel_id: str = None, status: str = None, limit: int = 100) -> list[dict]:
        query = {"user_id": user_id}
        if channel_id:
            query["channel_id"] = channel_id
        if status and status != "all":
            query["status"] = status
        return await self.find_many(query, limit=limit, sort=[("created_at", -1)])

    async def find_latest_by_channel(self, user_id: str, channel_id: str = None) -> dict | None:
        query = {"user_id": user_id}
        if channel_id:
            query["channel_id"] = channel_id
        results = await self.find_many(query, limit=1, sort=[("created_at", -1)])
        return results[0] if results else None

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

    async def find_by_video(self, video_id: str, channel_id: str = None) -> list[dict]:
        query = {"video_id": video_id}
        if channel_id:
            query["channel_id"] = channel_id
        return await self.find_many(query)

    async def find_by_channel(self, channel_id: str, user_id: str) -> list[dict]:
        return await self.find_many({"channel_id": channel_id, "user_id": user_id})

    async def create_asset(self, asset_data: dict) -> str:
        return await self.insert_one(asset_data)

    async def record_scene_provenance(
        self,
        user_id: str,
        channel_id: str,
        video_id: str,
        scene_id: str,
        pexels_id: int | None,
        photographer: str | None,
        photographer_url: str | None,
        video_url: str | None,
        download_url: str | None,
        width: int,
        height: int,
        duration: float,
        sha256: str,
        local_path: str,
        query: str,
        selected_at: str | None = None
    ) -> str:
        """Persists full provenance metadata for a scene video asset with strict channel isolation."""
        from datetime import datetime, timezone
        doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "video_id": video_id,
            "scene_id": scene_id,
            "asset_type": "stock_video",
            "provider": "pexels",
            "pexels_id": pexels_id,
            "photographer": photographer,
            "photographer_url": photographer_url,
            "video_url": video_url,
            "download_url": download_url,
            "width": width,
            "height": height,
            "duration": duration,
            "sha256": sha256,
            "local_path": local_path,
            "query": query,
            "selected_at": selected_at or datetime.now(timezone.utc).isoformat(),
        }
        return await self.insert_one(doc)

