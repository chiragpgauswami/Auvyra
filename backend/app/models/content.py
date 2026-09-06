from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional, Any

class ContentIdeaStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    in_production = "in_production"
    completed = "completed"
    archived = "archived"

class ContentIdea(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    title: str
    description: str = ""
    keywords: list[str] = []
    target_audience: str = ""
    estimated_views: int | None = None
    status: ContentIdeaStatus = ContentIdeaStatus.draft
    source: str = ""  # "ai_generated", "manual", "research"
    confidence: float = 0.0
    created_at: datetime
    updated_at: datetime

class ResearchOpportunity(BaseModel):
    topic: str
    why_now: str
    evidence: str
    content_gap: str
    recommended_angle: str
    hooks: list[str] = []
    sources: list[str] = []
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

class StructuredScript(BaseModel):
    title: str = ""
    hooks: list[str] = []
    hook_scores: dict[str, float] = {}
    selected_hook: str = ""
    outline: list[str] = []
    final_script: str
    cta: str = ""

class Script(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    content_idea_id: str | None = None
    title: str
    script_text: str
    duration_estimate: int = 0  # seconds
    word_count: int = 0
    version: int = 1
    status: str = "draft"  # draft, approved, recorded
    structured_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

class ResearchReport(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    channel_id: str
    topic: str
    findings: list[dict] = []
    sources: list[str] = []
    recommendations: list[str] = []
    opportunities: list[ResearchOpportunity] = []
    created_at: datetime
