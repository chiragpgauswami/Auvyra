from pydantic import BaseModel, Field
from datetime import datetime

class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    youtube_channel_id: str | None = None
    handle: str | None = None

class ChannelResponse(BaseModel):
    id: str
    user_id: str
    youtube_channel_id: str | None = None
    name: str
    handle: str | None = None
    description: str = ""
    thumbnail_url: str | None = None
    subscriber_count: int = 0
    video_count: int = 0
    view_count: int = 0
    status: str = "connected"  # connected, disconnected, pending
    autopilot_enabled: bool = False
    approval_required: bool = True
    created_at: datetime
    updated_at: datetime

class ChannelMemory(BaseModel):
    channel_id: str
    best_topics: list[dict] = []
    weak_topics: list[dict] = []
    best_hooks: list[dict] = []
    best_title_patterns: list[dict] = []
    best_video_lengths: list[dict] = []
    best_publish_times: list[dict] = []
    audience_insights: list[dict] = []
    strategy_insights: list[dict] = []
    last_updated: datetime
