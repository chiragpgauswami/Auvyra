from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class HookRule(BaseModel):
    hook_type: str = "curiosity_gap"
    pattern: str
    effectiveness_score: float = 0.5

class ContentPillar(BaseModel):
    name: str
    description: str = ""
    target_ratio: float = 0.25

class ChannelOnboardingRequest(BaseModel):
    niche: str = Field(..., min_length=2, max_length=150)
    target_audience: str = Field(..., min_length=2, max_length=250)
    tone: str = "engaging"  # entertaining, informative, provocative, fast-paced
    content_pillars: List[str] = []
    language: str = "en"
    target_geography: str = "US"
    reference_channels: List[str] = []
    custom_instructions: str = ""

class ChannelBrain(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    channel_id: str
    niche: str
    target_audience: str
    language: str = "en"
    geography: str = "US"
    tone: str = "engaging"
    positioning: str = ""
    content_pillars: List[ContentPillar] = []
    winning_topics: List[str] = []
    losing_topics: List[str] = []
    winning_hooks: List[HookRule] = []
    losing_hooks: List[str] = []
    winning_title_patterns: List[str] = []
    best_publish_times: List[str] = []
    learned_rules: List[str] = []
    strategy_version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChannelBrainResponse(BaseModel):
    id: str
    user_id: str
    channel_id: str
    niche: str
    target_audience: str
    language: str
    geography: str
    tone: str
    positioning: str
    content_pillars: List[ContentPillar]
    winning_topics: List[str]
    losing_topics: List[str]
    winning_hooks: List[HookRule]
    losing_hooks: List[str]
    winning_title_patterns: List[str]
    best_publish_times: List[str]
    learned_rules: List[str]
    strategy_version: int
    created_at: datetime
    updated_at: datetime

