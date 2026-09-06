from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository

class AnalyticsRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "analytics_snapshots")

    async def find_by_video(self, user_id: str, video_id: str) -> list[dict]:
        return await self.find_many({"user_id": user_id, "video_id": video_id})

    async def find_by_channel(self, user_id: str, channel_id: str, period: str = None) -> list[dict]:
        query = {"user_id": user_id, "channel_id": channel_id}
        if period:
            query["period"] = period
        return await self.find_many(query)

    async def create_snapshot(self, data: dict) -> str:
        return await self.insert_one(data)


class StrategyInsightRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "strategy_insights")

    async def find_by_channel(self, user_id: str, channel_id: str) -> list[dict]:
        return await self.find_many({"user_id": user_id, "channel_id": channel_id})

    async def create_insight(self, data: dict) -> str:
        return await self.insert_one(data)
