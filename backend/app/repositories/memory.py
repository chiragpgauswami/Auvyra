from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository

class AgentRunRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "agent_runs")

    async def record_run(self, agent_type: str, user_id: str, channel_id: str, input_data: dict, output_data: dict, duration_ms: int) -> str:
        data = {
            "agent_type": agent_type,
            "user_id": user_id,
            "channel_id": channel_id,
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": duration_ms
        }
        return await self.insert_one(data)

    async def find_recent(self, user_id: str, channel_id: str, limit: int = 10) -> list[dict]:
        return await self.find_many(
            {"user_id": user_id, "channel_id": channel_id},
            limit=limit,
            sort=[("created_at", -1)]
        )
