from typing import Dict, List, Optional, Any
from loguru import logger
from backend.app.ai.gateway import AIGateway
from backend.app.repositories.research import ResearchRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs
from backend.app.models.content import ResearchOpportunity

class ResearchService:
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.research_repo = ResearchRepository(db)
        self.ai = ai_gateway
    
    async def create_research(self, user_id: str, channel_id: str, topic: str, channel_context: Optional[dict] = None) -> dict:
        if not self.ai:
            raise ValueError("AI Gateway is not configured")
            
        # Generate structured content research validated via Pydantic ResearchOpportunity
        opportunity: ResearchOpportunity = await self.ai.generate_research_opportunity(topic, channel_context=channel_context)
        
        data = {
            "user_id": user_id,
            "channel_id": channel_id,
            "topic": topic,
            "findings": [
                {"title": "Why Now", "detail": opportunity.why_now},
                {"title": "Evidence", "detail": opportunity.evidence},
                {"title": "Content Gap", "detail": opportunity.content_gap},
                {"title": "Recommended Angle", "detail": opportunity.recommended_angle}
            ],
            "sources": opportunity.sources,
            "recommendations": opportunity.hooks,
            "opportunities": [opportunity.model_dump()],
            "confidence": opportunity.confidence
        }
        report_id = await self.research_repo.create_report(data)
        data["id"] = report_id
        return serialize_doc(data)
    
    async def list_research(self, user_id: str, channel_id: str) -> List[dict]:
        reports = await self.research_repo.find_by_channel(user_id=user_id, channel_id=channel_id)
        return serialize_docs(reports)
        
    async def get_research(self, user_id: str, report_id: str) -> Optional[dict]:
        report = await self.research_repo.find_by_id(report_id, user_id=user_id)
        return serialize_doc(report)