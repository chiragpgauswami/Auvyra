from pydantic import BaseModel, Field, model_validator
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
    topic: str = "Research Topic"
    content_pillar: str = ""
    target_audience: str = ""
    why_now: Any = ""
    evidence: Any = ""
    content_gap: Any = ""
    recommended_angle: Any = ""
    hooks: list[str] = []
    sources: list[str] = []
    opportunity_score: float = 85.0
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data: Any) -> Any:
        import json
        if isinstance(data, dict):
            if not data.get("topic"):
                data["topic"] = data.get("title") or "Research Topic"
            for field in ["why_now", "evidence", "content_gap", "recommended_angle"]:
                val = data.get(field)
                if isinstance(val, (dict, list)):
                    data[field] = json.dumps(val)
                elif val is not None:
                    data[field] = str(val)
                else:
                    data[field] = ""
            for list_field in ["hooks", "sources"]:
                val = data.get(list_field)
                if isinstance(val, str):
                    data[list_field] = [val]
                elif isinstance(val, list):
                    data[list_field] = [str(x) for x in val]
                else:
                    data[list_field] = []
        return data

class StructuredScript(BaseModel):
    title: str = ""
    hooks: list[str] = []
    hook_scores: dict[str, float] = {}
    selected_hook: str = ""
    outline: list[str] = []
    final_script: str = ""
    cta: str = ""

    @model_validator(mode="before")
    @classmethod
    def resolve_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("final_script"):
                data["final_script"] = data.get("script") or data.get("script_text") or ""
        return data

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
