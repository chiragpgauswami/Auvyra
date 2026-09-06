from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository

class ResearchRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "research_reports")

    async def find_by_channel(self, user_id: str, channel_id: str) -> list[dict]:
        return await self.find_many({"user_id": user_id, "channel_id": channel_id})

    async def create_report(self, report_data: dict) -> str:
        return await self.insert_one(report_data)
