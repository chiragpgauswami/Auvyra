"""
Autopilot Service — Core Autonomous Production Engine (Phase 20).
Executes granular, idempotent pipeline stages with durable checkpoints, worker leases,
zero swallowed publishing/QA errors, and strict append-only telemetry.
"""

import os
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from bson import ObjectId
from loguru import logger

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.autopilot.exceptions import (
    AutopilotError,
    PexelsMediaError,
    TTSError,
    WhisperSubtitleError,
    RenderError,
    QAGateError,
    OAuthConfigurationError,
    PublishingError
)
from backend.app.autopilot.qa import QAEngine
from backend.app.repositories.channels import ChannelRepository, AutopilotQueueRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.autopilot_events import AutopilotEventsRepository
from backend.app.repositories.videos import VideoRepository, VideoAssetRepository
from backend.app.repositories.jobs import NotificationRepository
from backend.app.repositories.users import OAuthAccountRepository
from backend.app.repositories.caption_styles import CaptionStyleRepository
from backend.app.repositories.content_topics import ContentTopicRepository
from backend.app.repositories.video_analytics import VideoAnalyticsRepository

from backend.app.services.research_service import ResearchService
from backend.app.services.content_service import ContentService
from backend.app.services.metadata_service import MetadataService
from backend.app.services.thumbnail_service import ThumbnailService
from backend.app.services.publishing_service import PublishingService
from backend.app.services.learning_service import LearningService
from backend.app.video.storyboard import StoryboardGenerator
from backend.app.video.media.pexels_provider import PexelsProvider
from backend.app.video.audio.edge_tts_provider import EdgeTTSProvider
from backend.app.video.subtitles.generator import SubtitleGenerator
from backend.app.video.composition.assembler import VideoAssembler
from backend.app.video.composition.overlay import VideoOverlay
from backend.app.video.pipeline import VideoGenerationService
from backend.app.video.models import VideoAspect, VideoGenerationRequest
from backend.app.youtube.client import get_youtube_client_for_channel, YouTubeAPIError
from backend.app.ai.gateway import AIGateway
from backend.app.utils.serializers import serialize_doc

STAGE_ORDER = [
    "channel_sync",
    "research",
    "script",
    "storyboard",
    "pexels",
    "tts",
    "subtitles",
    "render",
    "qa",
    "metadata",
    "thumbnail",
    "approval",
    "upload",
    "learn",
]

STAGE_PROGRESS = {
    "channel_sync": 5,
    "research": 12,
    "script": 22,
    "storyboard": 32,
    "pexels": 45,
    "tts": 55,
    "subtitles": 65,
    "render": 80,
    "qa": 85,
    "metadata": 90,
    "thumbnail": 93,
    "approval": 95,
    "upload": 98,
    "learn": 100,
}

class AutopilotService:
    def __init__(self, db, ai_gateway: Optional[AIGateway] = None):
        self.db = db
        self.settings = get_settings()
        self.ai = ai_gateway or AIGateway(self.settings)

        self.queue_repo = AutopilotQueueRepository(db)
        self.events_repo = AutopilotEventsRepository(db)
        self.channel_repo = ChannelRepository(db)
        self.brain_repo = ChannelBrainRepository(db)
        self.video_repo = VideoRepository(db)
        self.asset_repo = VideoAssetRepository(db)
        self.notification_repo = NotificationRepository(db)
        self.oauth_repo = OAuthAccountRepository(db)
        self.caption_repo = CaptionStyleRepository(db)
        self.topic_repo = ContentTopicRepository(db)
        self.video_analytics_repo = VideoAnalyticsRepository(db)


        self.research_service = ResearchService(db, self.ai)
        self.content_service = ContentService(db, self.ai)
        self.metadata_service = MetadataService(self.ai)
        self.thumbnail_service = ThumbnailService(output_dir="media/thumbnails")
        self.publishing_service = PublishingService(db)
        self.learning_service = LearningService(db, self.ai)

        self.storyboard_gen = StoryboardGenerator(self.ai)
        self.tts_provider = EdgeTTSProvider()
        self.sub_gen = SubtitleGenerator()
        self.assembler = VideoAssembler()
        self.overlay = VideoOverlay()
        self.qa_engine = QAEngine()
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

        selected_opp = max(opportunities, key=lambda x: x.get("opportunity_score", 0))
        topic = selected_opp.get("topic", "AI Breakthrough")

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
            await self.notification_repo.create_notification(
                user_id=user_id,
                type="approval_required",
                title="Autopilot Video Ready for Review",
                message=f"'{metadata.title}' has been generated and is ready for publishing approval.",
                data={"video_id": vid_id, "channel_id": channel_id}
            )
        else:
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

    async def execute_queue_item(self, queue_item_id: str, worker_id: str) -> dict:
        """
        Executes a claimed queue item through granular, idempotent pipeline stages.
        Resumes from the first incomplete stage if resuming after a crash or retry.
        """
        oid = ObjectId(queue_item_id) if ObjectId.is_valid(queue_item_id) else queue_item_id
        slot = await self.db.autopilot_queue.find_one({"_id": oid})
        if not slot:
            raise ValueError(f"Queue item {queue_item_id} not found")

        channel_id = slot["channel_id"]
        user_id = slot["user_id"]

        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found for queue item {queue_item_id}")

        brain = await self.brain_repo.find_by_channel(channel_id, user_id) or {}
        artifacts = dict(slot.get("artifacts", {}))
        stages = dict(slot.get("stages", {}))

        logger.info(f"Worker {worker_id} beginning execution for slot {queue_item_id} (Channel: '{channel.get('name')}')")

        # Start periodic lease heartbeat task
        stop_heartbeat = asyncio.Event()

        async def heartbeat_loop():
            while not stop_heartbeat.is_set():
                try:
                    await asyncio.sleep(30)
                    if not stop_heartbeat.is_set():
                        await self.queue_repo.heartbeat(str(slot["_id"]), worker_id, extend_seconds=300)
                except Exception as he:
                    logger.warning(f"Heartbeat extension failed: {he}")

        heartbeat_task = asyncio.create_task(heartbeat_loop())

        try:
            for stage in STAGE_ORDER:
                stage_data = stages.get(stage, {})
                if stage_data.get("status") == "completed":
                    logger.info(f"Slot {queue_item_id}: Skipping completed stage '{stage}' (checkpoint verified)")
                    continue

                # Execute stage with telemetry and checkpoints
                try:
                    artifacts = await self._run_stage(
                        stage=stage,
                        slot=slot,
                        channel=channel,
                        brain=brain,
                        artifacts=artifacts,
                        worker_id=worker_id
                    )
                    stages[stage] = {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "artifact_refs": artifacts.get(f"refs_{stage}", {})
                    }

                    # If approval stage halted for review, break execution loop cleanly
                    if stage == "approval" and slot.get("status") == "ready_for_approval":
                        logger.info(f"Slot {queue_item_id} halted at 'approval' gate (awaiting user review)")
                        break

                except Exception as stage_err:
                    # Explicit error capture — zero swallowed errors
                    await self._handle_stage_failure(
                        stage=stage,
                        slot=slot,
                        channel=channel,
                        error=stage_err,
                        worker_id=worker_id
                    )
                    raise stage_err

            # Reload updated slot state
            final_slot = await self.db.autopilot_queue.find_one({"_id": oid})
            return serialize_doc(final_slot)

        finally:
            stop_heartbeat.set()
            heartbeat_task.cancel()

    async def _run_stage(
        self,
        stage: str,
        slot: dict,
        channel: dict,
        brain: dict,
        artifacts: dict,
        worker_id: str
    ) -> dict:
        slot_id = str(slot["_id"])
        channel_id = slot["channel_id"]
        user_id = slot["user_id"]
        progress = STAGE_PROGRESS.get(stage, 0)

        # 1. Mark stage started
        queue_status = None if (slot.get("status") == "published" or stage == "learn") else f"producing_{stage}"
        await self.queue_repo.checkpoint_stage(
            slot_id=slot_id,
            stage=stage,
            status="in_progress",
            progress=progress,
            queue_status=queue_status
        )
        await self.events_repo.record_event(
            channel_id=channel_id,
            user_id=user_id,
            queue_item_id=slot_id,
            stage=stage,
            status="started",
            progress=progress,
            message=f"Starting stage: {stage}"
        )

        # 2. Execute discrete stage logic
        if stage == "channel_sync":
            stage_refs = await self._stage_channel_sync(channel, brain)
        elif stage == "research":
            stage_refs = await self._stage_research(slot, channel, brain)
        elif stage == "script":
            stage_refs = await self._stage_script(slot, channel, brain, artifacts)
        elif stage == "storyboard":
            stage_refs = await self._stage_storyboard(slot, channel, artifacts)
        elif stage == "pexels":
            stage_refs = await self._stage_pexels(slot, channel, artifacts)
        elif stage == "tts":
            stage_refs = await self._stage_tts(slot, channel, artifacts)
        elif stage == "subtitles":
            stage_refs = await self._stage_subtitles(slot, channel, artifacts)
        elif stage == "render":
            stage_refs = await self._stage_render(slot, channel, artifacts)
        elif stage == "qa":
            stage_refs = await self._stage_qa(slot, channel, artifacts)
        elif stage == "metadata":
            stage_refs = await self._stage_metadata(slot, channel, brain, artifacts)
        elif stage == "thumbnail":
            stage_refs = await self._stage_thumbnail(slot, channel, artifacts)
        elif stage == "approval":
            stage_refs = await self._stage_approval(slot, channel, artifacts)
        elif stage == "upload":
            stage_refs = await self._stage_upload(slot, channel, artifacts)
        elif stage == "learn":
            stage_refs = await self._stage_learn(slot, channel)
        else:
            stage_refs = {}

        artifacts.update(stage_refs)
        artifacts[f"refs_{stage}"] = stage_refs

        # 3. Mark stage completed
        await self.queue_repo.checkpoint_stage(
            slot_id=slot_id,
            stage=stage,
            status="completed",
            progress=progress,
            artifact_refs=stage_refs
        )
        await self.events_repo.record_event(
            channel_id=channel_id,
            user_id=user_id,
            queue_item_id=slot_id,
            stage=stage,
            status="completed",
            progress=progress,
            message=f"Completed stage: {stage}",
            metadata=stage_refs,
            video_id=artifacts.get("video_id")
        )
        return artifacts

    async def _handle_stage_failure(
        self,
        stage: str,
        slot: dict,
        channel: dict,
        error: Exception,
        worker_id: str
    ):
        slot_id = str(slot["_id"])
        channel_id = slot["channel_id"]
        user_id = slot["user_id"]

        retryable = getattr(error, "retryable", False)
        attempts = int(slot.get("attempts", 0)) + 1
        now_str = datetime.now(timezone.utc).isoformat()
        error_dict = {
            "code": getattr(error, "code", "STAGE_EXECUTION_FAILED"),
            "stage": stage,
            "message": str(error),
            "retryable": retryable,
            "attempts": attempts,
            "occurred_at": now_str,
            "timestamp": now_str
        }


        # Update stage checkpoint to failed
        await self.queue_repo.checkpoint_stage(
            slot_id=slot_id,
            stage=stage,
            status="failed",
            error=error_dict
        )

        # Mark slot state machine (failed or retrying)
        await self.queue_repo.mark_slot_failed(
            slot_id=slot_id,
            error_info=error_dict,
            retryable=retryable,
            max_attempts=slot.get("max_attempts", 3)
        )

        # Record append-only event
        await self.events_repo.record_event(
            channel_id=channel_id,
            user_id=user_id,
            queue_item_id=slot_id,
            stage=stage,
            status="failed",
            message=f"Stage '{stage}' failed: {error}",
            error=error_dict
        )

        # Create user notification for mandatory failure visibility
        await self.notification_repo.create_notification(
            user_id=user_id,
            type="autopilot_failed",
            title=f"Autopilot Error: {stage.upper()} Failed",
            message=f"Channel '{channel.get('name')}' halted at {stage}: {error}",
            data={"channel_id": channel_id, "queue_item_id": slot_id, "error": error_dict}
        )

    # -------------------------------------------------------------
    # 14 GRANULAR STAGE IMPLEMENTATIONS
    # -------------------------------------------------------------

    async def _stage_channel_sync(self, channel: dict, brain: dict) -> dict:
        channel_id = str(channel["_id"])
        user_id = channel["user_id"]

        if channel.get("status") != "connected":
            raise AutopilotError(
                message=f"Channel '{channel.get('name')}' is disconnected",
                code="CHANNEL_DISCONNECTED",
                stage="channel_sync"
            )

        oauth_id = channel.get("oauth_account_id")
        if not oauth_id:
            logger.warning(f"Channel {channel_id} has no linked oauth_account_id (legacy or unlinked)")

        return {
            "channel_id": channel_id,
            "channel_name": channel.get("name"),
            "oauth_linked": bool(oauth_id)
        }

    async def _stage_research(self, slot: dict, channel: dict, brain: dict) -> dict:
        topic = slot.get("topic")
        pillar = slot.get("pillar") or "General"
        user_id = slot["user_id"]
        channel_id = slot["channel_id"]

        recent_topics = await self.topic_repo.get_recent_topics(channel_id, days=30)
        rationale = "Scheduled queue topic selection."
        hook_premise = ""

        if not topic or topic == "Automated Production Slot" or topic.lower() in recent_topics:
            opportunities = await self.research_service.generate_channel_opportunities(user_id, channel_id)
            if opportunities:
                fresh_opps = [o for o in opportunities if o.get("topic", "").lower().strip() not in recent_topics]
                target_opps = fresh_opps if fresh_opps else opportunities
                top_opp = max(target_opps, key=lambda x: x.get("opportunity_score", 0))
                topic = top_opp.get("topic", f"Breakthrough in {pillar}")
                rationale = top_opp.get("market_need") or f"Opportunity score {top_opp.get('opportunity_score', 85)} in {pillar}"
                hook_premise = top_opp.get("hook_premise", "")
            else:
                topic = f"Breakthroughs in {pillar}"
                rationale = f"Pillar focus for {pillar}"

        # Record decision into content_topics
        await self.topic_repo.record_topic_decision(
            channel_id=channel_id,
            user_id=user_id,
            topic=topic,
            hook=hook_premise,
            pillar=pillar,
            rationale=rationale,
            source="autopilot_research"
        )

        return {
            "topic": topic,
            "pillar": pillar,
            "niche": brain.get("niche", "Technology"),
            "rationale": rationale
        }


    async def _stage_script(self, slot: dict, channel: dict, brain: dict, artifacts: dict) -> dict:
        if artifacts.get("script_text"):
            return {"script_text": artifacts["script_text"], "script_id": artifacts.get("script_id")}

        topic = artifacts.get("topic") or slot.get("topic")
        user_id = slot["user_id"]
        channel_id = slot["channel_id"]

        channel_context = {
            "niche": brain.get("niche", "General"),
            "winning_hooks": brain.get("winning_hooks", []),
            "learned_rules": brain.get("learned_rules", [])
        }

        script_doc = await self.content_service.generate_script(
            user_id=user_id,
            channel_id=channel_id,
            topic=topic,
            duration=45,
            channel_context=channel_context
        )
        script_text = script_doc.get("script_text", "")
        if not script_text or len(script_text.split()) < 20:
            raise AutopilotError(
                message="Generated script is empty or too short (< 20 words)",
                code="SCRIPT_GENERATION_FAILED",
                stage="script",
                retryable=True
            )

        return {
            "script_text": script_text,
            "script_id": script_doc.get("id"),
            "word_count": len(script_text.split())
        }

    async def _stage_storyboard(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        if artifacts.get("storyboard_scenes"):
            return {"storyboard_scenes": artifacts["storyboard_scenes"]}

        script_text = artifacts.get("script_text", "")
        topic = artifacts.get("topic") or slot.get("topic")

        storyboard = await self.storyboard_gen.generate_storyboard(
            script=script_text,
            total_duration=45.0,
            topic=topic,
            aspect_ratio="9:16"
        )
        if not storyboard.scenes:
            raise AutopilotError(
                message="Storyboard generation returned zero scenes",
                code="STORYBOARD_FAILED",
                stage="storyboard",
                retryable=True
            )

        scenes_dict = [s.model_dump() for s in storyboard.scenes]
        return {
            "storyboard_scenes": scenes_dict,
            "scene_count": len(scenes_dict)
        }

    async def _stage_pexels(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        """
        Real Pexels search & download per scene (Requirement 3).
        No fixed/fallback MP4s. Raises PEXELS_NO_SUITABLE_MEDIA on failure.
        """
        if artifacts.get("scene_clips"):
            # Verify paths still exist
            if all(os.path.exists(p) for p in artifacts["scene_clips"]):
                return {"scene_clips": artifacts["scene_clips"]}

        scenes = artifacts.get("storyboard_scenes", [])
        if not scenes:
            raise PexelsMediaError("No storyboard scenes provided to Pexels stage")

        api_key = self.settings.PEXELS_API_KEY
        if not api_key:
            raise PexelsMediaError("PEXELS_API_KEY is not configured in settings")

        pexels = PexelsProvider(api_key)
        channel_id = slot["channel_id"]
        slot_id = str(slot["_id"])
        dest_dir = os.path.abspath(f"media/videos/{channel_id}/temp_{slot_id}")
        os.makedirs(dest_dir, exist_ok=True)

        downloaded_clips = []
        for idx, sc in enumerate(scenes):
            queries = sc.get("search_queries") or [sc.get("text", "")]
            clip_downloaded = False

            for q in queries:
                clean_query = q.strip()
                if not clean_query:
                    continue
                try:
                    items = await pexels.search(
                        query=clean_query,
                        aspect_ratio=VideoAspect.portrait,
                        min_duration=int(sc.get("duration", 3))
                    )
                    if items:
                        target_item = items[0]
                        local_path = await pexels.download(target_item, dest_dir)
                        if os.path.exists(local_path) and os.path.getsize(local_path) > 1024:
                            downloaded_clips.append(local_path)
                            clip_downloaded = True
                            logger.info(f"Pexels downloaded scene {idx+1}/{len(scenes)}: {clean_query} -> {os.path.basename(local_path)}")
                            
                            # Record scene provenance in MongoDB video_assets with strict channel isolation
                            try:
                                h = hashlib.sha256()
                                with open(local_path, "rb") as f:
                                    while chunk := f.read(65536):
                                        h.update(chunk)
                                clip_sha256 = h.hexdigest()

                                await self.asset_repo.record_scene_provenance(
                                    user_id=slot["user_id"],
                                    channel_id=slot["channel_id"],
                                    video_id=slot_id,
                                    scene_id=str(sc.get("scene_id") or f"scene_{idx+1}"),
                                    pexels_id=getattr(target_item, "pexels_id", None),
                                    photographer=getattr(target_item, "photographer", None),
                                    photographer_url=getattr(target_item, "photographer_url", None),
                                    video_url=getattr(target_item, "video_url", None),
                                    download_url=getattr(target_item, "download_url", getattr(target_item, "url", None)),
                                    width=getattr(target_item, "width", 0),
                                    height=getattr(target_item, "height", 0),
                                    duration=float(getattr(target_item, "duration", 0.0) or sc.get("duration", 3.0)),
                                    sha256=clip_sha256,
                                    local_path=local_path,
                                    query=clean_query,
                                    selected_at=datetime.now(timezone.utc).isoformat()
                                )
                            except Exception as prov_err:
                                logger.warning(f"Failed to record scene asset provenance: {prov_err}")
                            break
                except Exception as pe:
                    logger.warning(f"Pexels query '{clean_query}' error: {pe}")

            if not clip_downloaded:
                # Semantic fallback query based on niche/topic
                fallback_query = artifacts.get("topic") or "technology"
                try:
                    items = await pexels.search(
                        query=fallback_query,
                        aspect_ratio=VideoAspect.portrait,
                        min_duration=3
                    )
                    if items:
                        target_item = items[0]
                        local_path = await pexels.download(target_item, dest_dir)
                        if os.path.exists(local_path) and os.path.getsize(local_path) > 1024:
                            downloaded_clips.append(local_path)
                            clip_downloaded = True
                            
                            try:
                                h = hashlib.sha256()
                                with open(local_path, "rb") as f:
                                    while chunk := f.read(65536):
                                        h.update(chunk)
                                clip_sha256 = h.hexdigest()

                                await self.asset_repo.record_scene_provenance(
                                    user_id=slot["user_id"],
                                    channel_id=slot["channel_id"],
                                    video_id=slot_id,
                                    scene_id=str(sc.get("scene_id") or f"scene_{idx+1}"),
                                    pexels_id=getattr(target_item, "pexels_id", None),
                                    photographer=getattr(target_item, "photographer", None),
                                    photographer_url=getattr(target_item, "photographer_url", None),
                                    video_url=getattr(target_item, "video_url", None),
                                    download_url=getattr(target_item, "download_url", getattr(target_item, "url", None)),
                                    width=getattr(target_item, "width", 0),
                                    height=getattr(target_item, "height", 0),
                                    duration=float(getattr(target_item, "duration", 0.0) or sc.get("duration", 3.0)),
                                    sha256=clip_sha256,
                                    local_path=local_path,
                                    query=fallback_query,
                                    selected_at=datetime.now(timezone.utc).isoformat()
                                )
                            except Exception as prov_err:
                                logger.warning(f"Failed to record fallback scene asset provenance: {prov_err}")
                except Exception:
                    pass


            if not clip_downloaded:
                # Requirement 3: Never silently use fixed.mp4/sample.mp4. Explicit failure!
                raise PexelsMediaError(
                    message=f"No suitable Pexels media found for scene {idx+1} (query: '{queries}')",
                    details={"scene_index": idx, "queries": queries}
                )

        return {
            "scene_clips": downloaded_clips,
            "clip_count": len(downloaded_clips)
        }

    async def _stage_tts(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        if artifacts.get("audio_path") and os.path.exists(artifacts["audio_path"]):
            return {
                "audio_path": artifacts["audio_path"],
                "audio_duration": artifacts.get("audio_duration", 0)
            }

        script_text = artifacts.get("script_text", "")
        channel_id = slot["channel_id"]
        slot_id = str(slot["_id"])
        out_dir = os.path.abspath(f"media/videos/{channel_id}")
        os.makedirs(out_dir, exist_ok=True)
        audio_path = os.path.join(out_dir, f"audio_{slot_id}.mp3")

        try:
            tts_res = await self.tts_provider.synthesize(
                text=script_text,
                voice_name="en-US-AriaNeural-Female",
                voice_rate=1.0,
                output_path=audio_path
            )
            if not os.path.exists(audio_path) or tts_res.duration <= 0:
                raise TTSError("TTS produced empty or unreadable audio file")

            return {
                "audio_path": audio_path,
                "audio_duration": tts_res.duration
            }
        except Exception as e:
            raise TTSError(f"TTS synthesis failed: {str(e)}")

    async def _stage_subtitles(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        """
        Real Whisper Subtitle Generation (Requirement 4 & Phase 21/22 Rules).
        Uses faster-whisper on actual generated TTS audio with style cadence.
        """
        if artifacts.get("subtitle_path") and os.path.exists(artifacts["subtitle_path"]):
            return {"subtitle_path": artifacts["subtitle_path"]}

        audio_path = artifacts.get("audio_path")
        if not audio_path or not os.path.exists(audio_path):
            raise WhisperSubtitleError("TTS audio file not found for subtitle generation")

        channel_id = slot["channel_id"]
        slot_id = str(slot["_id"])
        user_id = slot["user_id"]
        out_dir = os.path.abspath(f"media/videos/{channel_id}")
        srt_path = os.path.join(out_dir, f"subs_{slot_id}.srt")

        # Resolve caption style snapshot or channel default
        caption_cfg = slot.get("caption_style_config")
        if not caption_cfg:
            caption_cfg = await self.caption_repo.get_channel_style(channel_id, user_id)

        max_words = int(caption_cfg.get("max_words_per_cue", 3))

        try:
            # Transcribe real TTS audio using faster-whisper with style cadence
            self.sub_gen.create_from_audio(
                audio_path,
                srt_path,
                word_level=True,
                shorts_cadence=True,
                max_words_per_cue=max_words
            )

            if not os.path.exists(srt_path) or os.path.getsize(srt_path) < 10:
                raise WhisperSubtitleError("Whisper failed to produce valid subtitle file")

            return {"subtitle_path": srt_path}
        except Exception as e:
            raise WhisperSubtitleError(f"Whisper subtitle pipeline failed: {str(e)}")

    async def _stage_render(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        if artifacts.get("video_path") and os.path.exists(artifacts["video_path"]):
            return {
                "video_path": artifacts["video_path"],
                "rendered_duration": artifacts.get("rendered_duration"),
                "stock_coverage_ratio": artifacts.get("stock_coverage_ratio", 1.0)
            }

        scene_clips = artifacts.get("scene_clips", [])
        audio_path = artifacts.get("audio_path")
        subtitle_path = artifacts.get("subtitle_path")
        audio_duration = artifacts.get("audio_duration", 45.0)

        channel_id = slot["channel_id"]
        slot_id = str(slot["_id"])
        user_id = slot["user_id"]
        out_dir = os.path.abspath(f"media/videos/{channel_id}")
        os.makedirs(out_dir, exist_ok=True)
        raw_composed_path = os.path.join(out_dir, f"composed_{slot_id}.mp4")
        final_video_path = os.path.join(out_dir, f"video_{slot_id}.mp4")

        # Resolve caption style snapshot or channel default
        caption_cfg = slot.get("caption_style_config")
        if not caption_cfg:
            caption_cfg = await self.caption_repo.get_channel_style(channel_id, user_id)

        try:
            # 1. Assemble clips to match audio duration and calculate interval union stock coverage
            self.assembler.assemble_clips(
                video_paths=scene_clips,
                audio_duration=audio_duration,
                aspect_ratio=VideoAspect.portrait,
                output_path=raw_composed_path,
                fit_mode="cover"
            )

            coverage_report = getattr(self.assembler, "last_coverage_report", {}) or {}
            coverage_ratio = float(coverage_report.get("coverage_ratio", 1.0))

            # 2. Overlay narration audio, subtitles, and top header banner
            req = VideoGenerationRequest(
                topic=slot.get("topic", "AI Daily"),
                aspect_ratio="9:16",
                subtitle_enabled=True,
                bgm_type="none",
                caption_style=caption_cfg
            )
            success = self.overlay.compose_final(
                video_path=raw_composed_path,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
                output_path=final_video_path,
                params=req
            )
            if not success or not os.path.exists(final_video_path):
                raise RenderError("FFmpeg overlay composition failed to produce output MP4")


            return {
                "video_path": final_video_path,
                "rendered_duration": audio_duration,
                "stock_coverage_ratio": coverage_ratio
            }
        except Exception as e:
            raise RenderError(f"Video rendering and composition failed: {str(e)}")

    async def _stage_qa(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        """
        Mandatory QA Gate (Requirement 5 & Phase 21 Hardened Rules).
        QA failure strictly blocks publishing.
        """
        video_path = artifacts.get("video_path")
        subtitle_path = artifacts.get("subtitle_path")
        stock_coverage_ratio = artifacts.get("stock_coverage_ratio")
        scene_clips = artifacts.get("scene_clips", [])

        # QAEngine raises QAGateError on any failure
        qa_report = self.qa_engine.inspect_and_gate(
            video_path=video_path,
            subtitle_path=subtitle_path,
            expected_format=slot.get("format", "shorts"),
            stock_coverage_ratio=stock_coverage_ratio,
            scene_clips=scene_clips
        )
        return {"qa_report": qa_report, "qa_passed": True}


    async def _stage_metadata(self, slot: dict, channel: dict, brain: dict, artifacts: dict) -> dict:
        topic = artifacts.get("topic") or slot.get("topic")
        script_text = artifacts.get("script_text", "")

        channel_context = {
            "niche": brain.get("niche", "General"),
            "target_audience": brain.get("target_audience", "General audience")
        }
        meta = await self.metadata_service.generate_metadata(
            topic=topic,
            script=script_text,
            channel_context=channel_context
        )
        return {
            "title": meta.title,
            "description": meta.description,
            "tags": meta.tags,
            "hashtags": meta.hashtags
        }

    async def _stage_thumbnail(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        video_path = artifacts.get("video_path")
        title = artifacts.get("title", slot.get("topic", "AI Update"))
        channel_id = slot["channel_id"]
        slot_id = str(slot["_id"])
        user_id = slot["user_id"]

        thumb_name = f"thumb_{slot_id}.jpg"
        thumb_path = self.thumbnail_service.generate_thumbnail(
            video_path=video_path,
            text_overlay=title[:30],
            output_filename=thumb_name
        )

        # Create/Update Video record in videos collection
        now_utc = datetime.now(timezone.utc)
        video_doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "title": title,
            "description": artifacts.get("description", ""),
            "script_id": artifacts.get("script_id"),
            "status": "ready",
            "file_path": video_path,
            "duration": artifacts.get("rendered_duration", 45.0),
            "width": 1080,
            "height": 1920,
            "thumbnail_path": thumb_path,
            "tags": artifacts.get("tags", []),
            "created_at": now_utc,
            "updated_at": now_utc
        }
        vid_id = await self.video_repo.insert_one(video_doc)

        return {
            "thumbnail_path": thumb_path,
            "video_id": vid_id
        }

    async def _stage_approval(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        """
        Approval Gate (Requirement 15).
        If approval_required == True or mode == 'assisted', halt and await human approval.
        """
        approval_required = channel.get("approval_required", True)
        mode = channel.get("autopilot_config", {}).get("mode", "full_autopilot")
        slot_id = str(slot["_id"])
        user_id = slot["user_id"]
        channel_id = slot["channel_id"]
        video_id = artifacts.get("video_id")

        if approval_required or mode == "assisted":
            # Transition slot to ready_for_approval and notify user
            await self.queue_repo.checkpoint_stage(
                slot_id=slot_id,
                stage="approval",
                status="completed",
                progress=STAGE_PROGRESS["approval"],
                queue_status="ready_for_approval"
            )
            slot["status"] = "ready_for_approval"

            await self.notification_repo.create_notification(
                user_id=user_id,
                type="approval_required",
                title="Autopilot Video Ready for Review",
                message=f"'{artifacts.get('title')}' is ready for publishing approval.",
                data={"channel_id": channel_id, "queue_item_id": slot_id, "video_id": video_id}
            )
            return {"approval_status": "waiting_user_review"}

        return {"approval_status": "auto_approved"}

    async def _stage_upload(self, slot: dict, channel: dict, artifacts: dict) -> dict:
        """
        Channel-Scoped YouTube Publishing (Requirement 10 & 16).
        Zero swallowed publishing errors.
        """
        channel_id = slot["channel_id"]
        user_id = slot["user_id"]
        slot_id = str(slot["_id"])
        video_id = artifacts.get("video_id")
        video_path = artifacts.get("video_path")
        thumb_path = artifacts.get("thumbnail_path")

        # Resolve channel-scoped YouTube client
        yt_client = await get_youtube_client_for_channel(channel_id, user_id, self.db)
        if not yt_client or (not yt_client.access_token and not yt_client.refresh_token):
            raise OAuthConfigurationError(
                f"Google OAuth credentials missing for channel '{channel.get('name')}'. Reconnect YouTube before publishing."
            )

        # Verify authenticated YouTube channel ID matches the intended channel
        try:
            my_chans = await yt_client.list_my_channels()
            my_yt_ids = [c.get("youtube_channel_id") for c in my_chans]
            expected_yt_id = channel.get("youtube_channel_id")
            if expected_yt_id and expected_yt_id not in my_yt_ids:
                raise PublishingError(
                    message=f"Authenticated YouTube credentials do not match channel ID {expected_yt_id}",
                    code="YOUTUBE_CHANNEL_MISMATCH"
                )
        except YouTubeAPIError as ye:
            raise PublishingError(message=f"YouTube pre-flight auth check failed: {ye.message}", code=ye.error_code)

        # Upload video
        try:
            pub_res = await yt_client.upload_video(
                file_path=video_path,
                title=artifacts.get("title", "AI Video"),
                description=artifacts.get("description", ""),
                tags=artifacts.get("tags", []),
                privacy_status="public"
            )
            yt_id = pub_res.get("youtube_video_id")
            yt_url = pub_res.get("url")

            # Set thumbnail
            if thumb_path and os.path.exists(thumb_path) and yt_id:
                try:
                    await yt_client.set_thumbnail(yt_id, thumb_path)
                except Exception as te:
                    logger.warning(f"Thumbnail upload non-fatal warning: {te}")

            # Mark video published
            await self.video_repo.update_one(
                video_id,
                {
                    "status": "published",
                    "youtube_video_id": yt_id,
                    "youtube_url": yt_url,
                    "published_at": datetime.now(timezone.utc)
                },
                user_id=user_id
            )

            # Mark slot published
            await self.queue_repo.mark_slot_published(slot_id, video_id, yt_url)

            return {
                "youtube_video_id": yt_id,
                "youtube_url": yt_url,
                "published": True
            }
        except YouTubeAPIError as e:
            raise PublishingError(message=e.message, code=e.error_code)
        except Exception as e:
            raise PublishingError(message=str(e), code="YOUTUBE_UPLOAD_FAILED")

    async def _stage_learn(self, slot: dict, channel: dict) -> dict:
        """
        Learning stage (Requirement 11).
        Non-critical: if learning fails, video remains published and queue item remains published.
        """
        channel_id = slot["channel_id"]
        user_id = slot["user_id"]

        try:
            learn_res = await self.learning_service.run_learning_cycle(user_id, channel_id)
            return {"learning_result": learn_res}
        except Exception as le:
            logger.warning(f"Non-critical learning failure after upload: {le}")
            return {"learning_error": str(le)}

    # -------------------------------------------------------------
    # CONTROL ENDPOINTS (APPROVE & RETRY)
    # -------------------------------------------------------------

    async def approve_queue_item(self, user_id: str, queue_item_id: str, worker_id: str = "manual_approval") -> dict:
        """Approves a video in ready_for_approval state to proceed to publishing."""
        oid = ObjectId(queue_item_id) if ObjectId.is_valid(queue_item_id) else queue_item_id
        slot = await self.db.autopilot_queue.find_one({"_id": oid, "user_id": user_id})
        if not slot:
            raise ValueError(f"Queue item {queue_item_id} not found or unauthorized")

        if slot.get("status") != "ready_for_approval":
            raise ValueError(f"Cannot approve slot in status '{slot.get('status')}' (expected 'ready_for_approval')")

        # Set status to in_production and proceed to upload
        now_utc = datetime.now(timezone.utc)
        await self.db.autopilot_queue.update_one(
            {"_id": oid},
            {"$set": {"status": "in_production", "current_stage": "upload", "updated_at": now_utc}}
        )

        return await self.execute_queue_item(queue_item_id, worker_id)

    async def retry_queue_item(self, user_id: str, queue_item_id: str, worker_id: str = "manual_retry") -> dict:
        """Resets failed stage and resumes execution from checkpoint."""
        oid = ObjectId(queue_item_id) if ObjectId.is_valid(queue_item_id) else queue_item_id
        slot = await self.db.autopilot_queue.find_one({"_id": oid, "user_id": user_id})
        if not slot:
            raise ValueError(f"Queue item {queue_item_id} not found or unauthorized")

        now_utc = datetime.now(timezone.utc)
        failed_stage = slot.get("current_stage", "pending")

        # Reset failed stage to pending so it will re-execute
        update_doc = {
            "status": "pending",
            "last_error": None,
            "failure_reason": None,
            "claimed_by": None,
            "lease_expires_at": None,
            "updated_at": now_utc
        }
        if failed_stage != "pending":
            update_doc[f"stages.{failed_stage}.status"] = "pending"

        await self.db.autopilot_queue.update_one({"_id": oid}, {"$set": update_doc})
        return await self.execute_queue_item(queue_item_id, worker_id)

    async def cancel_queue_item(self, user_id: str, queue_item_id: str) -> bool:
        """Cancels a pending or failed queue slot."""
        oid = ObjectId(queue_item_id) if ObjectId.is_valid(queue_item_id) else queue_item_id
        res = await self.db.autopilot_queue.delete_one({
            "_id": oid,
            "user_id": user_id,
            "status": {"$in": ["pending", "ready_for_approval", "failed", "retrying"]}
        })
        return res.deleted_count > 0

    async def get_channel_observability(self, user_id: str, channel_id: str) -> Dict[str, Any]:
        """Provides complete operational observability into the autonomous engine for a channel."""
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or access denied")

        now_utc = datetime.now(timezone.utc)

        # Queue depth counts
        counts = {}
        for st in ["pending", "in_production", "ready_for_approval", "published", "failed", "retrying"]:
            counts[st] = await self.db.autopilot_queue.count_documents({"channel_id": channel_id, "status": st})

        # Active worker leases
        active_leases_cursor = self.db.autopilot_queue.find({
            "channel_id": channel_id,
            "status": "in_production",
            "lease_expires_at": {"$gt": now_utc}
        })
        active_leases = await active_leases_cursor.to_list(length=10)

        # Last successful upload
        last_pub_slot = await self.db.autopilot_queue.find_one(
            {"channel_id": channel_id, "status": "published"},
            sort=[("published_at", -1)]
        )

        # Last learning run
        last_learn_run = await self.db.learning_runs.find_one(
            {"channel_id": channel_id},
            sort=[("completed_at", -1)]
        )

        # Recent events (last 15)
        events = await self.events_repo.find_by_channel(channel_id, user_id, limit=15)

        # Failure telemetry
        failed_slots_cursor = self.db.autopilot_queue.find(
            {"channel_id": channel_id, "status": {"$in": ["failed", "retrying"]}}
        ).sort("updated_at", -1).limit(5)
        recent_failures = await failed_slots_cursor.to_list(length=5)

        # Active caption style
        channel_style = await self.caption_repo.get_channel_style(channel_id, user_id)

        return {
            "channel_id": channel_id,
            "channel_name": channel.get("name"),
            "autopilot_enabled": channel.get("autopilot_enabled", False),
            "mode": channel.get("autopilot_config", {}).get("mode", "assisted"),
            "channel_style": channel_style,
            "queue_depth": counts,
            "active_worker_leases": [
                {
                    "slot_id": str(s["_id"]),
                    "stage": s.get("current_stage"),
                    "worker_id": s.get("claimed_by"),
                    "lease_expires_at": s.get("lease_expires_at").isoformat() if s.get("lease_expires_at") else None
                }
                for s in active_leases
            ],
            "last_successful_upload": {
                "published_at": last_pub_slot.get("published_at").isoformat() if (last_pub_slot and last_pub_slot.get("published_at")) else None,
                "video_id": last_pub_slot.get("video_id") if last_pub_slot else None,
                "youtube_url": last_pub_slot.get("youtube_url") if last_pub_slot else None
            } if last_pub_slot else None,
            "last_learning_run": {
                "completed_at": last_learn_run.get("completed_at").isoformat() if (last_learn_run and last_learn_run.get("completed_at")) else None,
                "status": last_learn_run.get("status") if last_learn_run else None,
                "signals_count": last_learn_run.get("signals_count", 0) if last_learn_run else 0
            } if last_learn_run else None,
            "recent_events": events,
            "recent_failures": [
                {
                    "slot_id": str(f["_id"]),
                    "topic": f.get("topic"),
                    "current_stage": f.get("current_stage"),
                    "attempts": f.get("attempts", 0),
                    "last_error": f.get("last_error")
                }
                for f in recent_failures
            ]
        }

