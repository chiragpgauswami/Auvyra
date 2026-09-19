from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from backend.app.repositories.base import BaseRepository

class ChannelBrainRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db, "channel_brains")

    async def find_by_channel(self, channel_id: str, user_id: str) -> Optional[dict]:
        """Find channel brain scoped by channel_id and user_id for strict multi-tenant isolation."""
        return await self.collection.find_one({"channel_id": channel_id, "user_id": user_id})

    async def upsert_brain(self, channel_id: str, user_id: str, brain_data: dict) -> dict:
        """Upsert channel brain document ensuring strict isolation."""
        now = datetime.now(timezone.utc)
        brain_data["updated_at"] = now
        brain_data.setdefault("created_at", now)
        brain_data["user_id"] = user_id
        brain_data["channel_id"] = channel_id

        await self.collection.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {"$set": brain_data},
            upsert=True
        )
        return await self.find_by_channel(channel_id, user_id)

    async def add_learned_rule(self, channel_id: str, user_id: str, rule: str) -> bool:
        res = await self.collection.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {
                "$addToSet": {"learned_rules": rule},
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$inc": {"strategy_version": 1}
            }
        )
        return res.modified_count > 0

    async def record_performance_topic(self, channel_id: str, user_id: str, topic: str, is_winning: bool) -> bool:
        field = "winning_topics" if is_winning else "losing_topics"
        res = await self.collection.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {
                "$addToSet": {field: topic},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        return res.modified_count > 0

    async def add_winning_hook(self, channel_id: str, user_id: str, hook: str) -> bool:
        res = await self.collection.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {
                "$addToSet": {"winning_hooks": hook},
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$inc": {"strategy_version": 1}
            }
        )
        return res.modified_count > 0

    async def update_structured_signals(self, channel_id: str, user_id: str, signals: List[Dict[str, Any]]) -> bool:
        """Stores evidence-backed structured insights into ChannelBrain."""
        res = await self.collection.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {
                "$set": {
                    "structured_signals": signals,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$inc": {"strategy_version": 1}
            }
        )
        return res.modified_count > 0


