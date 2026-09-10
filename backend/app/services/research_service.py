from typing import Dict, List, Optional, Any
from loguru import logger
from backend.app.ai.gateway import AIGateway
from backend.app.repositories.research import ResearchRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.channels import ChannelRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs
from backend.app.models.content import ResearchOpportunity

class ResearchService:
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.db = db
        self.research_repo = ResearchRepository(db)
        self.brain_repo = ChannelBrainRepository(db)
        self.channel_repo = ChannelRepository(db)
        self.ai = ai_gateway
    
    async def create_research(self, user_id: str, channel_id: str, topic: str, channel_context: Optional[dict] = None) -> dict:
        if not self.ai:
            raise ValueError("AI Gateway is not configured")

        if not channel_context:
            brain = await self.brain_repo.find_by_channel(channel_id, user_id)
            channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
            channel_context = {
                "channel_name": channel.get("name") if channel else "",
                "niche": brain.get("niche") if brain else (channel.get("name") if channel else "General"),
                "positioning": brain.get("positioning") if brain else "",
                "target_audience": brain.get("target_audience") if brain else "YouTube Shorts Audience",
                "content_pillars": [p.get("name") if isinstance(p, dict) else str(p) for p in (brain.get("content_pillars", []) if brain else [])],
                "winning_hooks": brain.get("winning_hooks", []) if brain else [],
                "learned_rules": brain.get("learned_rules", []) if brain else []
            }

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

    async def generate_channel_opportunities(self, user_id: str, channel_id: str, count: int = 5) -> List[dict]:
        """Generate structured AI Opportunity Feed strictly grounded in Channel Brain."""
        if not self.ai:
            raise ValueError("AI Gateway is not configured")

        brain = await self.brain_repo.find_by_channel(channel_id, user_id)
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        channel_context = {
            "channel_id": channel_id,
            "channel_name": channel.get("name", ""),
            "niche": brain.get("niche") if brain else channel.get("name", "General"),
            "positioning": brain.get("positioning") if brain else "",
            "target_audience": brain.get("target_audience") if brain else "YouTube Audience",
            "tone": brain.get("tone") if brain else "engaging",
            "content_pillars": brain.get("content_pillars", []) if brain else [{"name": channel.get("name")}],
            "winning_hooks": brain.get("winning_hooks", []) if brain else [],
            "learned_rules": brain.get("learned_rules", []) if brain else []
        }

        opportunities: List[ResearchOpportunity] = await self.ai.generate_opportunity_feed(channel_context, count=count)
        serialized_opps = []
        for opp in opportunities:
            opp_dict = opp.model_dump()
            opp_dict["channel_id"] = channel_id
            report_data = {
                "user_id": user_id,
                "channel_id": channel_id,
                "topic": opp.topic,
                "findings": [
                    {"title": "Why Now", "detail": opp.why_now},
                    {"title": "Evidence", "detail": opp.evidence},
                    {"title": "Content Gap", "detail": opp.content_gap},
                    {"title": "Recommended Angle", "detail": opp.recommended_angle}
                ],
                "sources": opp.sources,
                "recommendations": opp.hooks,
                "opportunities": [opp_dict],
                "confidence": opp.confidence
            }
            report_id = await self.research_repo.create_report(report_data)
            opp_dict["report_id"] = report_id
            opp_dict["id"] = report_id
            serialized_opps.append(opp_dict)

        return serialized_opps
    
    async def list_research(self, user_id: str, channel_id: str) -> List[dict]:
        reports = await self.research_repo.find_by_channel(user_id=user_id, channel_id=channel_id)
        return serialize_docs(reports)
        
    async def get_research(self, user_id: str, report_id: str) -> Optional[dict]:
        report = await self.research_repo.find_by_id(report_id, user_id=user_id)
        return serialize_doc(report)