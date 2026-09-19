from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    retrying = "retrying"

class JobType(str, Enum):
    video_generation = "video_generation"
    research = "research"
    script_generation = "script_generation"
    publishing = "publishing"
    analytics_sync = "analytics_sync"
    learning = "learning"
    autopilot_orchestration = "autopilot_orchestration"
    autopilot_stage = "autopilot_stage"

class Job(BaseModel):
    id: str = Field(alias="_id")
    type: JobType
    user_id: str
    channel_id: str | None = None
    status: JobStatus = JobStatus.queued
    progress: int = 0  # 0-100
    payload: dict = {}
    result: dict | None = None
    attempts: int = 0
    max_attempts: int = 3
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

class AutopilotEvent(BaseModel):
    id: str = Field(alias="_id", default=None)
    channel_id: str
    user_id: str
    queue_item_id: str
    stage: str
    status: str  # "started", "progress", "completed", "failed", "retrying"
    progress: int = 0
    message: str = ""
    metadata: dict = Field(default_factory=dict)
    error: dict | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Notification(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    type: str  # "job_complete", "job_failed", "video_published", etc.
    title: str
    message: str
    read: bool = False
    data: dict = {}
    created_at: datetime
