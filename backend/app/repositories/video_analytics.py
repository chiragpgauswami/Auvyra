from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.repositories.base import BaseRepository

class VideoAnalyticsRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db, "video_analytics_snapshots")

    async def record_snapshot(
        self,
        user_id: str,
        channel_id: str,
        video_id: str,
        metrics: dict,
        youtube_video_id: Optional[str] = None,
        source: str = "youtube_analytics_v2",
        api_version: str = "v2",
        collected_at: Optional[datetime] = None
    ) -> str:
        """Records an immutable, timestamped analytics snapshot for a video."""
        now = collected_at or datetime.now(timezone.utc)
        doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "video_id": str(video_id),
            "youtube_video_id": youtube_video_id,
            "collected_at": now,
            "metrics": metrics,
            "source": source,
            "api_version": api_version,
            "created_at": now
        }
        res = await self.collection.insert_one(doc)
        return str(res.inserted_id)

    async def get_latest_snapshot(self, channel_id: str, video_id: str, user_id: str) -> Optional[dict]:
        """Fetches the latest analytics snapshot for a specific video ensuring channel isolation."""
        doc = await self.collection.find_one(
            {"channel_id": channel_id, "video_id": str(video_id), "user_id": user_id},
            sort=[("collected_at", -1)]
        )
        if doc:
            doc["id"] = str(doc.pop("_id", ""))
        return doc

    async def get_video_history(
        self,
        channel_id: str,
        video_id: str,
        user_id: str,
        limit: int = 30
    ) -> List[dict]:
        """Returns time series historical snapshots for a video."""
        cursor = self.collection.find(
            {"channel_id": channel_id, "video_id": str(video_id), "user_id": user_id}
        ).sort("collected_at", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for d in docs:
            d["id"] = str(d.pop("_id", ""))
        return docs

    async def get_channel_aggregate_summary(self, channel_id: str, user_id: str) -> Dict[str, Any]:
        """Calculates channel-level aggregates from latest snapshots of each video."""
        pipeline = [
            {"$match": {"channel_id": channel_id, "user_id": user_id}},
            {"$sort": {"collected_at": -1}},
            {
                "$group": {
                    "_id": "$video_id",
                    "latest_doc": {"$first": "$$ROOT"}
                }
            },
            {
                "$replaceRoot": {"newRoot": "$latest_doc"}
            }
        ]
        cursor = self.collection.aggregate(pipeline)
        latest_snaps = await cursor.to_list(length=500)

        total_views = sum(s.get("metrics", {}).get("views", 0) for s in latest_snaps)
        total_likes = sum(s.get("metrics", {}).get("likes", 0) for s in latest_snaps)
        total_comments = sum(s.get("metrics", {}).get("comments", 0) for s in latest_snaps)
        total_watch_hours = sum(s.get("metrics", {}).get("watch_time_hours", 0.0) for s in latest_snaps)
        avg_ctr = (
            sum(s.get("metrics", {}).get("ctr", 0.0) for s in latest_snaps) / len(latest_snaps)
            if latest_snaps else 0.0
        )

        return {
            "channel_id": channel_id,
            "tracked_videos_count": len(latest_snaps),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_watch_time_hours": round(total_watch_hours, 2),
            "avg_ctr": round(avg_ctr, 2)
        }

