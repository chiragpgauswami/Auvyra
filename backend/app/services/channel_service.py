import hashlib
import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger
from backend.app.repositories.channels import (
    ChannelRepository,
    ChannelMemoryRepository,
    AutopilotQueueRepository,
    NicheCacheRepository
)
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.caption_styles import CaptionStyleRepository
from backend.app.models.channel import AutopilotConfig, AutopilotMode, ContentFormat
from backend.app.ai.gateway import AIGateway
from backend.app.config import get_settings
from backend.app.utils.serializers import serialize_doc, serialize_docs

class ChannelService:
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.memory_repo = ChannelMemoryRepository(db)
        self.brain_repo = ChannelBrainRepository(db)
        self.queue_repo = AutopilotQueueRepository(db)
        self.niche_cache_repo = NicheCacheRepository(db)
        self.caption_repo = CaptionStyleRepository(db)
        self.ai_gateway = ai_gateway or AIGateway(get_settings())

    
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

    async def get_niche_recommendations(self, user_id: str, channel_id: str, refresh: bool = False) -> list[dict]:
        """Fetch AI-assisted niche recommendations tailored to the channel, leveraging cache."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or unauthorized")

        brain = await self.brain_repo.find_by_channel(channel_id, user_id=user_id)
        
        # Build deterministic context hash for caching
        context_string = f"{channel.get('name')}:{channel.get('description')}:{brain.get('niche') if brain else ''}"
        context_hash = hashlib.sha256(context_string.encode()).hexdigest()

        if not refresh:
            cached = await self.niche_cache_repo.get_cached(channel_id, context_hash)
            if cached and cached.get("recommendations"):
                return cached["recommendations"]

        channel_context = {
            "name": channel.get("name"),
            "description": channel.get("description"),
            "handle": channel.get("handle"),
            "subscriber_count": channel.get("subscriber_count", 0),
            "video_count": channel.get("video_count", 0),
            "brain": brain or {}
        }

        recommendations = await self.ai_gateway.generate_niche_recommendations(channel_context)
        await self.niche_cache_repo.save_cache(channel_id, user_id, context_hash, recommendations, ttl_seconds=86400)
        return recommendations

    async def configure_autopilot(self, user_id: str, channel_id: str, config_data: dict) -> dict:
        """Validate, persist AutopilotConfig, update Channel Brain, and bootstrap initial persistent queue."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or unauthorized")

        # Validate configuration schema
        config = AutopilotConfig.model_validate(config_data)

        # Validate frequency against selected schedule slots
        total_slots = len(config.schedule.days_of_week) * len(config.schedule.times)
        if config.schedule.frequency_per_week > total_slots:
            raise ValueError(
                f"Requested frequency ({config.schedule.frequency_per_week}/week) exceeds available schedule slots ({total_slots}/week). "
                f"Please select more days or times to support this frequency."
            )

        now = datetime.now(timezone.utc)
        current_cfg = channel.get("autopilot_config") or {}
        new_version = current_cfg.get("config_version", 0) + 1

        config.config_version = new_version
        config.created_at = current_cfg.get("created_at") or now
        config.updated_at = now

        # Update channel document
        await self.channel_repo.update_one(
            channel_id,
            {
                "autopilot_config": config.model_dump(),
                "autopilot_enabled": (config.mode != AutopilotMode.off),
                "approval_required": config.approval_required,
                "updated_at": now
            },
            user_id=user_id
        )

        # Update structured Channel Brain (Requirement 7)
        chosen_niche = config.custom_niche if config.custom_niche else config.niche
        pillars = config.content_pillars or [chosen_niche]
        pillar_objects = [
            {"name": p, "description": f"Content pillar covering {p}", "target_ratio": round(1.0 / max(len(pillars), 1), 2)}
            for p in pillars
        ]

        existing_brain = await self.brain_repo.find_by_channel(channel_id, user_id=user_id)
        current_pos = existing_brain.get("positioning") if existing_brain else None
        positioning = current_pos or f"The premier high-retention vertical channel for {chosen_niche}."

        brain_payload = {
            "user_id": user_id,
            "channel_id": channel_id,
            "niche": chosen_niche,
            "target_audience": config.target_audience,
            "language": config.language,
            "geography": config.target_geography,
            "tone": config.tone,
            "positioning": positioning,
            "content_pillars": pillar_objects,
            "winning_topics": existing_brain.get("winning_topics", []) if existing_brain else [],
            "losing_topics": existing_brain.get("losing_topics", []) if existing_brain else [],
            "winning_hooks": existing_brain.get("winning_hooks", []) if existing_brain else [],
            "losing_hooks": existing_brain.get("losing_hooks", []) if existing_brain else [],
            "winning_title_patterns": existing_brain.get("winning_title_patterns", []) if existing_brain else [],
            "best_publish_times": existing_brain.get("best_publish_times", []) if existing_brain else [],
            "learned_rules": existing_brain.get("learned_rules", []) if existing_brain else [],
            "format_strategy": {
                "format": config.format.value,
                "aspect_ratio": "9:16" if config.format == ContentFormat.shorts else "16:9",
                "target_duration_seconds": 45 if config.format == ContentFormat.shorts else 300
            },
            "publishing_strategy": {
                "frequency_per_week": config.schedule.frequency_per_week,
                "timezone": config.schedule.timezone,
                "days_of_week": config.schedule.days_of_week,
                "times": config.schedule.times,
                "mode": config.mode.value,
                "approval_required": config.approval_required,
                "privacy_status": config.privacy_status
            },
            "strategy_version": new_version,
            "last_updated": now
        }
        await self.brain_repo.upsert_brain(channel_id, user_id, brain_payload)

        # Enqueue initial persistent content queue (Requirement 5 & 6)
        created_count = 0
        if config.mode != AutopilotMode.off:
            local_tz = zoneinfo.ZoneInfo(config.schedule.timezone)
            now_local = datetime.now(local_tz)

            # Resolve active caption style for snapshotting
            style_id = getattr(config, "caption_style", "bold") or "bold"
            preset = self.caption_repo.get_preset(style_id)
            if preset:
                active_style_cfg = await self.caption_repo.save_channel_style(channel_id, user_id, preset["config"])
            else:
                active_style_cfg = await self.caption_repo.get_channel_style(channel_id, user_id)

            candidate_slots = []
            for day_offset in range(1, 8):
                cand_date = now_local.date() + timedelta(days=day_offset)
                if cand_date.weekday() in config.schedule.days_of_week:
                    for t_str in config.schedule.times:
                        h, m = map(int, t_str.split(":"))
                        cand_dt = datetime(cand_date.year, cand_date.month, cand_date.day, h, m, tzinfo=local_tz)
                        candidate_slots.append(cand_dt)

            candidate_slots.sort()
            selected_slots = candidate_slots[:config.schedule.frequency_per_week]

            for i, slot_local in enumerate(selected_slots):
                slot_utc = slot_local.astimezone(timezone.utc)
                pillar = pillars[i % len(pillars)]
                topic_premise = f"{pillar}: Essential Insight #{i + 1}"

                # Idempotency protection: don't create duplicate slots for the same channel at the same scheduled_at
                existing_slot = await self.queue_repo.find_slot(channel_id, slot_utc)
                if not existing_slot:
                    slot_doc = {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "scheduled_at": slot_utc,
                        "local_time_display": slot_local.strftime("%A, %b %d at %I:%M %p %Z"),
                        "timezone": config.schedule.timezone,
                        "format": config.format.value,
                        "pillar": pillar,
                        "topic": topic_premise,
                        "caption_style_config": active_style_cfg,
                        "status": "pending",
                        "priority": 1,
                        "source": "autopilot_bootstrap",
                        "config_version": new_version,
                        "created_at": now,
                        "updated_at": now,
                        "production_job_id": None
                    }
                    await self.queue_repo.create_slot(slot_doc)
                    created_count += 1


        # Invalidate niche recommendations cache on reconfiguration
        await self.niche_cache_repo.invalidate(channel_id)

        bootstrap_job_id = f"job_bootstrap_{channel_id}_v{new_version}"
        return {
            "status": "success",
            "channel_id": channel_id,
            "bootstrap_job_id": bootstrap_job_id,
            "config_version": new_version,
            "autopilot_mode": config.mode.value,
            "scheduled_slots_count": created_count,
            "message": f"Autopilot successfully configured in '{config.mode.value}' mode. {created_count} persistent schedule slots created.",
            "config": config.model_dump()
        }

    async def get_autopilot_config(self, user_id: str, channel_id: str) -> dict:
        """Fetch Autopilot configuration, active status, and upcoming queue summary."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or unauthorized")

        config = channel.get("autopilot_config")
        upcoming = await self.queue_repo.find_by_channel(channel_id, user_id, status="pending", limit=10)
        return {
            "channel_id": channel_id,
            "autopilot_enabled": channel.get("autopilot_enabled", False),
            "approval_required": channel.get("approval_required", True),
            "config": config,
            "upcoming_queue_count": len(upcoming),
            "upcoming_slots": serialize_docs(upcoming)
        }

    async def get_autopilot_queue(self, user_id: str, channel_id: str, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        """Fetch persistent scheduled queue items for a channel."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or unauthorized")
        items = await self.queue_repo.find_by_channel(channel_id, user_id, status=status, limit=limit)
        return serialize_docs(items)