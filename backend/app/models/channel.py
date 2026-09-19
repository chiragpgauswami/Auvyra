from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator


class AutopilotMode(str, Enum):
    off = "off"
    assisted = "assisted"
    full_autopilot = "full_autopilot"


class ContentFormat(str, Enum):
    shorts = "shorts"
    longform = "longform"
    hybrid = "hybrid"


class PublishSchedule(BaseModel):
    days_of_week: list[int] = Field(default=[0, 2, 4], description="0=Monday ... 6=Sunday")
    times: list[str] = Field(default=["17:00"], description="HH:MM in local timezone")
    timezone: str = Field(default="UTC", description="IANA timezone name, e.g. America/New_York")
    frequency_per_week: int = Field(default=3, ge=1, le=28)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        import zoneinfo
        try:
            zoneinfo.ZoneInfo(v)
            return v
        except Exception:
            raise ValueError(f"Invalid IANA timezone: '{v}'. Example valid timezones: 'UTC', 'America/New_York', 'Asia/Kolkata', 'Europe/London'.")

    @field_validator("times")
    @classmethod
    def validate_times(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one publishing time must be specified.")
        for t in v:
            parts = t.split(":")
            if len(parts) != 2 or not (0 <= int(parts[0]) <= 23) or not (0 <= int(parts[1]) <= 59):
                raise ValueError(f"Invalid time format: '{t}'. Must be HH:MM in 24-hour format.")
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("At least one day of the week must be selected.")
        for d in v:
            if d < 0 or d > 6:
                raise ValueError(f"Day of week must be between 0 (Monday) and 6 (Sunday), got {d}")
        return sorted(list(set(v)))


class AutopilotConfig(BaseModel):
    niche: str = Field(min_length=1)
    custom_niche: str | None = None
    format: ContentFormat = ContentFormat.shorts
    schedule: PublishSchedule
    target_audience: str = "General YouTube Audience"
    tone: str = "engaging"
    language: str = "en"
    target_geography: str = "US"
    content_pillars: list[str] = Field(default_factory=list)
    mode: AutopilotMode = AutopilotMode.assisted
    approval_required: bool = True
    privacy_status: str = "private"  # private, unlisted, public
    caption_style: str = "bold"
    tags: list[str] = Field(default_factory=list)
    config_version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NicheRecommendation(BaseModel):
    id: str
    name: str
    description: str
    market_demand: str  # "Very High", "High", "Growing"
    competition_level: str  # "Low", "Medium", "Moderate"
    opportunity_score: int = Field(ge=0, le=100)  # AI/heuristic calculated opportunity index
    target_audience: str
    suggested_pillars: list[str]
    recommended_format: str = "shorts"
    style_sample: str = ""
    source: str = "ollama"  # "ollama" | "curated_heuristic"
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class AutopilotQueueItem(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    scheduled_at: datetime
    local_time_display: str = ""
    timezone: str = "UTC"
    format: str = "shorts"
    pillar: str
    topic: str
    caption_style_config: dict[str, Any] | None = None
    status: str = "pending"  # pending, in_production, researching, scripting, storyboarding, media, tts, subtitles, rendering, qa, ready_for_approval, publishing, published, retrying, failed
    priority: int = 1
    source: str = "autopilot_bootstrap"
    config_version: int = 1
    created_at: datetime
    updated_at: datetime
    production_job_id: str | None = None
    stages: dict[str, dict] = Field(default_factory=dict)
    current_stage: str = "pending"
    progress: int = 0
    claimed_at: datetime | None = None
    claimed_by: str | None = None
    heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    attempts: int = 0
    max_attempts: int = 3
    last_error: dict | None = None
    failure_reason: str | None = None
    video_id: str | None = None
    published_at: datetime | None = None
    youtube_url: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)



class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    youtube_channel_id: str | None = None
    handle: str | None = None
    oauth_account_id: str | None = None


class ChannelResponse(BaseModel):
    id: str
    user_id: str
    youtube_channel_id: str | None = None
    oauth_account_id: str | None = None
    google_account_email: str | None = None
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
    autopilot_config: AutopilotConfig | None = None
    last_synced_at: datetime | None = None
    next_sync_at: datetime | None = None
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
