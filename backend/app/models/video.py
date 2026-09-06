from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class VideoStatus(str, Enum):
    queued = "queued"
    generating = "generating"
    generated = "generated"
    publishing = "publishing"
    published = "published"
    failed = "failed"

class Video(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    title: str
    description: str = ""
    script_id: str | None = None
    status: VideoStatus = VideoStatus.queued
    file_path: str | None = None  # e.g. "media/videos/channel_123/video_456.mp4"
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = None
    thumbnail_path: str | None = None
    youtube_video_id: str | None = None
    published_at: datetime | None = None
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime

class VideoAsset(BaseModel):
    id: str = Field(alias="_id")
    video_id: str
    user_id: str
    asset_type: str  # "audio", "subtitle", "bgm", "thumbnail", "source_clip"
    file_path: str
    duration: float | None = None
    created_at: datetime
