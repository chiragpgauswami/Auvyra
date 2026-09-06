from pydantic import BaseModel, Field
from datetime import datetime

class AnalyticsSnapshot(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    video_id: str | None = None
    period: str = "daily"  # daily, weekly, monthly
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    watch_time_hours: float = 0.0
    subscribers_gained: int = 0
    ctr: float = 0.0  # click-through rate
    avg_view_duration: float = 0.0
    snapshot_date: datetime
    created_at: datetime

class StrategyInsight(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    insight_type: str  # "topic", "timing", "format", "audience"
    title: str
    description: str
    source: str  # "analytics", "ai_analysis", "competitor"
    confidence: float = 0.0  # 0.0 to 1.0
    supporting_metrics: dict = {}
    actionable: bool = True
    created_at: datetime
