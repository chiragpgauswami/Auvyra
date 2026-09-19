from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from backend.app.repositories.base import BaseRepository

class ContentTopicRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db, "content_topics")

    async def record_topic_decision(
        self,
        channel_id: str,
        user_id: str,
        topic: str,
        hook: str = "",
        pillar: str = "",
        rationale: str = "",
        source: str = "ai_opportunity",
        used_in_video_id: Optional[str] = None
    ) -> str:
        """Records a selected content topic decision with full audit rationale."""
        now = datetime.now(timezone.utc)
        doc = {
            "channel_id": channel_id,
            "user_id": user_id,
            "topic": topic.strip(),
            "hook": hook.strip(),
            "pillar": pillar.strip(),
            "rationale": rationale.strip(),
            "source": source,
            "selected_at": now,
            "used_in_video_id": used_in_video_id,
            "created_at": now
        }
        res = await self.collection.insert_one(doc)
        return str(res.inserted_id)

    async def get_recent_topics(self, channel_id: str, days: int = 30) -> List[str]:
        """Returns list of unique topic strings selected within the past N days for duplication avoidance."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cursor = self.collection.find(
            {
                "channel_id": channel_id,
                "selected_at": {"$gte": cutoff}
            },
            {"topic": 1}
        )
        docs = await cursor.to_list(length=200)
        return [d["topic"].lower().strip() for d in docs if d.get("topic")]

    async def is_topic_recent(self, channel_id: str, topic: str, days: int = 30) -> bool:
        """Checks if a topic or similar topic was already selected within the window."""
        recent = await self.get_recent_topics(channel_id, days=days)
        topic_lower = topic.lower().strip()
        return topic_lower in recent

    async def list_channel_topics(self, channel_id: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.collection.find(
            {"channel_id": channel_id, "user_id": user_id}
        ).sort("selected_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["id"] = str(d.pop("_id", ""))
        return docs

