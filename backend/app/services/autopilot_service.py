import os
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from loguru import logger

from backend.app.repositories.channels import ChannelRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.repositories.jobs import NotificationRepository
from backend.app.services.research_service import ResearchService
from backend.app.services.content_service import ContentService
from backend.app.services.metadata_service import MetadataService
from backend.app.services.thumbnail_service import ThumbnailService
from backend.app.services.publishing_service import PublishingService
from backend.app.services.learning_service import LearningService
from backend.app.video.pipeline import VideoGenerationService
from backend.app.video.models import VideoGenerationRequest
from backend.app.ai.gateway import AIGateway
from backend.app.config import get_settings
from backend.app.utils.serializers import serialize_doc

class AutopilotService:
    """End-to-end autonomous orchestrator: Research -> Script -> Storyboard -> Video -> Thumbnail -> Publish -> Learn."""

    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.db = db
        self.ai = ai_gateway or AIGateway()
        self.settings = get_settings()

        self.channel_repo = ChannelRepository(db)
        self.brain_repo = ChannelBrainRepository(db)
        self.video_repo = VideoRepository(db)
        self.notification_repo = NotificationRepository(db)

        self.research_service = ResearchService(db, self.ai)
        self.content_service = ContentService(db, self.ai)
        self.metadata_service = MetadataService(self.ai)
        self.thumbnail_service = ThumbnailService(output_dir="media/thumbnails")
        self.publishing_service = PublishingService(db)
        self.learning_service = LearningService(db, self.ai)
        self.video_generation_service = VideoGenerationService(ai_client=self.ai)

    async def toggle_autopilot(self, user_id: str, channel_id: str, enabled: bool, approval_required: bool = True) -> dict:
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or access denied")

        update_data = {
            "autopilot_enabled": enabled,
            "approval_required": approval_required,
            "updated_at": datetime.now(timezone.utc)
        }
        await self.channel_repo.update_one(channel_id, update_data, user_id=user_id)
        channel.update(update_data)
        return serialize_doc(channel)

    async def run_autopilot_cycle(self, user_id: str, channel_id: str) -> dict:
        """Executes one complete autonomous YouTube cycle for a channel."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or access denied")

        logger.info(f"Starting Autopilot Cycle for channel '{channel.get('name')}' ({channel_id})")

        # 1. Channel Brain Context
        brain = await self.brain_repo.find_by_channel(channel_id, user_id)
        channel_context = {
            "niche": brain.get("niche", "General") if brain else "General",
            "winning_hooks": brain.get("winning_hooks", []) if brain else [],
            "learned_rules": brain.get("learned_rules", []) if brain else []
        }

        # 2. Research & Opportunity Selection
        opportunities = await self.research_service.generate_channel_opportunities(user_id, channel_id)
        if not opportunities:
            raise RuntimeError("Research engine did not produce any valid opportunities")

        # Select highest scoring opportunity
        selected_opp = max(opportunities, key=lambda x: x.get("opportunity_score", 0))
        topic = selected_opp.get("topic", "AI Breakthrough")
        logger.info(f"Autopilot selected top opportunity: '{topic}' (score: {selected_opp.get('opportunity_score')})")

        # 3. Script Generation
        script_doc = await self.content_service.generate_script(
            user_id=user_id,
            channel_id=channel_id,
            topic=topic,
            duration=45,
            channel_context=channel_context
        )
        script_text = script_doc.get("script_text", "")
        script_id = script_doc.get("id")

        # 4. Metadata Generation
        metadata = await self.metadata_service.generate_metadata(
            topic=topic,
            script=script_text,
            channel_context=channel_context
        )

        # 5. Video Generation & Composition
        output_dir = os.path.abspath(f"media/videos/{channel_id}")
        os.makedirs(output_dir, exist_ok=True)

        req = VideoGenerationRequest(
            topic=topic,
            script=script_text,
            duration=45,
            aspect_ratio="9:16",
            output_dir=output_dir
        )
        video_result = await self.video_generation_service.generate(req)

        # 6. Dynamic Thumbnail Generation
        thumb_filename = f"thumb_{os.path.splitext(os.path.basename(video_result.video_path))[0]}.jpg"
        thumbnail_path = self.thumbnail_service.generate_thumbnail(
            video_path=video_result.video_path,
            text_overlay=metadata.thumbnail_text_overlay or metadata.title[:30],
            output_filename=thumb_filename
        )

        # 7. Record Video in DB
        video_doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "title": metadata.title,
            "description": metadata.description,
            "script_id": script_id,
            "status": "ready",
            "file_path": video_result.video_path,
            "duration": video_result.duration,
            "width": video_result.width,
            "height": video_result.height,
            "size_bytes": video_result.size_bytes,
            "thumbnail_path": thumbnail_path,
            "tags": metadata.tags,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        vid_id = await self.video_repo.insert_one(video_doc)
        video_doc["id"] = vid_id

        # 8. Publishing / Approval Decision
        approval_required = channel.get("approval_required", True)
        publish_result = None

        if approval_required:
            # Create notification for user review
            await self.notification_repo.create_notification(
                user_id=user_id,
                type="approval_required",
                title="Autopilot Video Ready for Review",
                message=f"'{metadata.title}' has been generated and is ready for publishing approval.",
                data={"video_id": vid_id, "channel_id": channel_id}
            )
            logger.info(f"Autopilot video {vid_id} queued for user review (approval_required=True)")
        else:
            # Fully autonomous: Create job and publish
            try:
                pub_job = await self.publishing_service.create_publishing_job(
                    user_id=user_id,
                    video_id=vid_id,
                    metadata={
                        "title": metadata.title,
                        "description": metadata.description,
                        "tags": metadata.tags,
                        "thumbnail_path": thumbnail_path,
                        "privacy": "public"
                    }
                )
                publish_result = await self.publishing_service.execute_publish(user_id, pub_job["id"])
                logger.info(f"Autopilot published video {vid_id} to YouTube: {publish_result.get('url')}")
            except Exception as pe:
                logger.warning(f"Autopilot automated publish blocked or failed: {pe}")

        # 9. Trigger Learning Cycle to close loop
        try:
            learning_result = await self.learning_service.run_learning_cycle(user_id, channel_id)
        except Exception as le:
            logger.warning(f"Learning cycle execution non-fatal warning: {le}")
            learning_result = {}

        return {
            "status": "completed",
            "channel_id": channel_id,
            "video_id": vid_id,
            "title": metadata.title,
            "topic": topic,
            "duration": video_result.duration,
            "video_path": video_result.video_path,
            "thumbnail_path": thumbnail_path,
            "approval_required": approval_required,
            "publish_result": publish_result,
            "learning_result": learning_result
        }
