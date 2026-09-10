from typing import Dict, List, Optional
from loguru import logger
from backend.app.repositories.channels import ChannelRepository, ChannelMemoryRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.ai.gateway import AIGateway
from backend.app.config import get_settings
from backend.app.utils.serializers import serialize_doc, serialize_docs

class ChannelService:
    def __init__(self, db):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.memory_repo = ChannelMemoryRepository(db)
        self.brain_repo = ChannelBrainRepository(db)
        self.ai_gateway = AIGateway(get_settings())
    
    async def create_channel(self, user_id: str, data: dict) -> dict:
        data["user_id"] = user_id
        channel_id = await self.channel_repo.insert_one(data)
        data["id"] = channel_id
        return serialize_doc(data)
        
    async def list_channels(self, user_id: str, skip: int = 0, limit: int = 50) -> List[dict]:
        channels = await self.channel_repo.find_by_user(user_id=user_id, skip=skip, limit=limit)
        return serialize_docs(channels)
        
    async def get_channel(self, user_id: str, channel_id: str) -> Optional[dict]:
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        return serialize_doc(channel)
        
    async def update_channel(self, user_id: str, channel_id: str, data: dict) -> bool:
        return await self.channel_repo.update_one(channel_id, data, user_id=user_id)
        
    async def delete_channel(self, user_id: str, channel_id: str) -> bool:
        return await self.channel_repo.delete_one(channel_id, user_id=user_id)
        
    async def get_memory(self, user_id: str, channel_id: str) -> Optional[dict]:
        channel = await self.get_channel(user_id, channel_id)
        if not channel:
            return None
        memory = await self.memory_repo.get_memory(channel_id)
        return serialize_doc(memory)
        
    async def toggle_autopilot(self, user_id: str, channel_id: str, enabled: bool) -> bool:
        return await self.channel_repo.update_one(channel_id, {"autopilot_enabled": enabled}, user_id=user_id)

    async def onboard_channel(self, user_id: str, channel_id: str, onboarding_data: dict) -> dict:
        """Execute AI onboarding for a channel, establishing its persistent Channel Brain."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found for user {user_id}")

        # Generate intelligent strategy using AI Gateway
        ai_strategy = await self.ai_gateway.generate_channel_brain_strategy(onboarding_data)

        brain_payload = {
            "user_id": user_id,
            "channel_id": channel_id,
            "niche": onboarding_data.get("niche", channel.get("name", "General")),
            "target_audience": onboarding_data.get("target_audience", "General YouTube Audience"),
            "language": onboarding_data.get("language", "en"),
            "geography": onboarding_data.get("target_geography", "US"),
            "tone": onboarding_data.get("tone", "engaging"),
            "positioning": ai_strategy.get("positioning", ""),
            "content_pillars": ai_strategy.get("content_pillars", []),
            "winning_topics": [],
            "losing_topics": [],
            "winning_hooks": ai_strategy.get("winning_hooks", []),
            "losing_hooks": [],
            "winning_title_patterns": ai_strategy.get("winning_title_patterns", []),
            "best_publish_times": ai_strategy.get("best_publish_times", []),
            "learned_rules": ai_strategy.get("learned_rules", []),
            "strategy_version": 1
        }

        saved_brain = await self.brain_repo.upsert_brain(channel_id, user_id, brain_payload)
        logger.info(f"Successfully onboarded Channel Brain for channel {channel_id}")
        return serialize_doc(saved_brain)

    async def get_brain(self, user_id: str, channel_id: str) -> Optional[dict]:
        """Fetch isolated channel brain."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            return None
        brain = await self.brain_repo.find_by_channel(channel_id, user_id=user_id)
        return serialize_doc(brain)

    async def rebuild_brain(self, user_id: str, channel_id: str) -> dict:
        """Regenerate strategy for existing channel brain based on learned patterns."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        current_brain = await self.brain_repo.find_by_channel(channel_id, user_id=user_id)
        niche = current_brain.get("niche", channel.get("name")) if current_brain else channel.get("name")
        audience = current_brain.get("target_audience", "YouTube Audience") if current_brain else "YouTube Audience"
        tone = current_brain.get("tone", "engaging") if current_brain else "engaging"

        onboarding_input = {
            "niche": niche,
            "target_audience": audience,
            "tone": tone,
            "content_pillars": [p.get("name") if isinstance(p, dict) else str(p) for p in (current_brain.get("content_pillars", []) if current_brain else [])]
        }

        new_strategy = await self.ai_gateway.generate_channel_brain_strategy(onboarding_input)
        version = (current_brain.get("strategy_version", 1) + 1) if current_brain else 1

        updated_brain = {
            "user_id": user_id,
            "channel_id": channel_id,
            "niche": niche,
            "target_audience": audience,
            "tone": tone,
            "positioning": new_strategy.get("positioning", current_brain.get("positioning", "") if current_brain else ""),
            "content_pillars": new_strategy.get("content_pillars", current_brain.get("content_pillars", []) if current_brain else []),
            "winning_hooks": new_strategy.get("winning_hooks", current_brain.get("winning_hooks", []) if current_brain else []),
            "winning_title_patterns": new_strategy.get("winning_title_patterns", current_brain.get("winning_title_patterns", []) if current_brain else []),
            "best_publish_times": new_strategy.get("best_publish_times", current_brain.get("best_publish_times", []) if current_brain else []),
            "learned_rules": current_brain.get("learned_rules", []) if current_brain else new_strategy.get("learned_rules", []),
            "strategy_version": version
        }

        saved = await self.brain_repo.upsert_brain(channel_id, user_id, updated_brain)
        return serialize_doc(saved)