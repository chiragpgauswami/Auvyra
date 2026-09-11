from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
from loguru import logger
from backend.app.ai.gateway import AIGateway
from backend.app.repositories.analytics import AnalyticsRepository, StrategyInsightRepository
from backend.app.repositories.channels import ChannelRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.youtube.client import YouTubeClient, YouTubeAPIError, get_youtube_client_for_user, get_youtube_client_for_channel
from backend.app.utils.serializers import serialize_doc, serialize_docs

class AnalyticsService:
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.db = db
        self.analytics_repo = AnalyticsRepository(db)
        self.insight_repo = StrategyInsightRepository(db)
        self.channel_repo = ChannelRepository(db)
        self.video_repo = VideoRepository(db)
        self.ai = ai_gateway
    
    async def get_channel_analytics(self, user_id: str, channel_id: str, period: Optional[str] = None) -> List[dict]:
        snapshots = await self.analytics_repo.find_by_channel(user_id, channel_id, period=period)
        return serialize_docs(snapshots)
        
    async def get_video_analytics(self, user_id: str, video_id: str) -> List[dict]:
        snapshots = await self.analytics_repo.find_by_video(user_id, video_id)
        return serialize_docs(snapshots)
        
    async def create_snapshot(self, user_id: str, data: dict) -> dict:
        data["user_id"] = user_id
        data.setdefault("created_at", datetime.now(timezone.utc))
        data.setdefault("snapshot_date", datetime.now(timezone.utc))
        data.setdefault("views", 0)
        data.setdefault("likes", 0)
        data.setdefault("comments", 0)
        data.setdefault("shares", 0)
        data.setdefault("watch_time_hours", 0.0)
        data.setdefault("subscribers_gained", 0)
        data.setdefault("ctr", 0.0)
        data.setdefault("avg_view_duration", 0.0)
        
        snapshot_id = await self.analytics_repo.create_snapshot(data)
        data["id"] = snapshot_id
        return serialize_doc(data)

    async def sync_channel_analytics(self, user_id: str, channel_id: str, start_date: Optional[str] = None) -> dict:
        """Ingests real analytics metrics from YouTube Analytics API v2."""
        channel = await self.channel_repo.find_by_id(channel_id)
        if not channel or channel.get("user_id") != user_id:
            raise ValueError("Channel not found or unauthorized")

        yt_channel_id = channel.get("youtube_channel_id")
        yt_client = await get_youtube_client_for_channel(channel_id, user_id, self.db)
        if not yt_client or not yt_client.access_token:
            raise YouTubeAPIError(
                message="YouTube channel is not connected via OAuth. Connect your channel in Channels before syncing analytics.",
                status_code=400,
                error_code="GOOGLE_OAUTH_NOT_CONFIGURED"
            )

        if not start_date:
            # Default to last 30 days
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            reports = await yt_client.get_channel_reports(
                channel_id=yt_channel_id or "MINE",
                start_date=start_date,
                end_date=end_date,
                metrics=["views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained", "likes", "comments", "shares"]
            )
        except Exception as e:
            logger.error(f"Error calling YouTube Analytics API for channel {channel_id}: {e}")
            raise

        rows = reports.get("rows", [])
        headers = [h.get("name") for h in reports.get("columnHeaders", [])]

        synced_count = 0
        total_views = 0
        total_watch_hours = 0.0

        if rows:
            for row in rows:
                row_dict = dict(zip(headers, row))
                views = int(row_dict.get("views", 0))
                min_watched = float(row_dict.get("estimatedMinutesWatched", 0.0))
                avd = float(row_dict.get("averageViewDuration", 0.0))
                subs = int(row_dict.get("subscribersGained", 0))
                likes = int(row_dict.get("likes", 0))
                comments = int(row_dict.get("comments", 0))
                shares = int(row_dict.get("shares", 0))

                watch_hours = round(min_watched / 60.0, 2)
                total_views += views
                total_watch_hours += watch_hours

                # Create daily snapshot
                snapshot_doc = {
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "period": "daily",
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "shares": shares,
                    "watch_time_hours": watch_hours,
                    "subscribers_gained": subs,
                    "avg_view_duration": avd,
                    "ctr": round((likes / max(views, 1)) * 10.0, 2),  # Engagement CTR proxy if YouTube impressions private
                    "snapshot_date": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc)
                }
                await self.analytics_repo.create_snapshot(snapshot_doc)
                synced_count += 1

        # Refresh insights based on newly synced data
        await self.generate_insights(user_id, channel_id)

        return {
            "status": "success",
            "channel_id": channel_id,
            "synced_snapshots": synced_count,
            "total_views": total_views,
            "total_watch_hours": total_watch_hours
        }
        
    async def get_insights(self, user_id: str, channel_id: str) -> List[dict]:
        insights = await self.insight_repo.find_by_channel(user_id, channel_id)
        return serialize_docs(insights)
        
    async def generate_insights(self, user_id: str, channel_id: str) -> List[dict]:
        analytics_data = await self.get_channel_analytics(user_id, channel_id)
        insights_raw = []
        if self.ai:
            try:
                insights_raw = await self.ai.analyze_performance({"channel_id": channel_id, "snapshots": analytics_data})
                if isinstance(insights_raw, dict):
                    insights_raw = insights_raw.get("insights", [])
            except Exception as e:
                logger.warning(f"AI performance analysis fallback: {e}")
                
        if not insights_raw and analytics_data:
            total_views = sum(s.get("views", 0) for s in analytics_data)
            avg_views = total_views / len(analytics_data) if analytics_data else 0
            avg_ctr = (sum(s.get("ctr", 0.0) for s in analytics_data) / len(analytics_data)) if analytics_data else 0.0
            top_snapshot = max(analytics_data, key=lambda s: s.get("views", 0))

            insights_raw = [
                {
                    "title": "Channel Performance Aggregates",
                    "description": f"Analyzed {len(analytics_data)} snapshot(s): Total views {total_views}, average views per period {avg_views:.1f}, average CTR {avg_ctr:.2f}%.",
                    "source": "analytics_engine",
                    "confidence": 0.95,
                    "supporting_metrics": {
                        "sample_size": len(analytics_data),
                        "total_views": total_views,
                        "avg_views": round(avg_views, 1),
                        "avg_ctr": round(avg_ctr, 2),
                        "top_video_id": top_snapshot.get("video_id")
                    }
                }
            ]
        elif not insights_raw:
            insights_raw = []
            
        created = []
        now = datetime.now(timezone.utc)
        for insight in insights_raw:
            doc = {
                "user_id": user_id,
                "channel_id": channel_id,
                "title": insight.get("title", "Insight"),
                "description": insight.get("description", ""),
                "source": insight.get("source", "ai_analysis"),
                "confidence": float(insight.get("confidence", 0.8)),
                "supporting_metrics": insight.get("supporting_metrics", {}),
                "created_at": now
            }
            ins_id = await self.insight_repo.create_insight(doc)
            doc["id"] = ins_id
            created.append(serialize_doc(doc))
        return created
