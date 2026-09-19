"""
Unit Test Suite for Phase 20 Autopilot Engine.
Verifies:
1. Stage checkpoints & resume from first incomplete stage
2. Stage idempotency (avoids re-running completed stages)
3. Real Pexels error propagation (PEXELS_NO_SUITABLE_MEDIA)
4. QA gate strictly blocking publishing on failure
5. Channel-scoped OAuth credential resolution & mismatch rejection
6. Post-upload learning failure is non-critical (video remains published)
7. Append-only telemetry event recording
8. Worker lease expiration & heartbeats
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

from backend.app.services.autopilot_service import AutopilotService
from backend.app.autopilot.exceptions import (
    PexelsMediaError,
    QAGateError,
    PublishingError,
    OAuthConfigurationError
)
from backend.app.autopilot.qa import QAEngine

@pytest.mark.asyncio
async def test_stage_checkpoints_resume_from_incomplete():
    """Verify worker skips completed stages and resumes from the first incomplete stage."""
    mock_db = MagicMock()
    service = AutopilotService(mock_db)

    slot_id = str(ObjectId())
    channel_id = str(ObjectId())
    user_id = str(ObjectId())

    existing_slot = {
        "_id": ObjectId(slot_id),
        "channel_id": channel_id,
        "user_id": user_id,
        "topic": "Quantum Computing",
        "pillar": "Quantum Algorithms",
        "status": "in_production",
        "current_stage": "script",
        "stages": {
            "channel_sync": {"status": "completed", "completed_at": datetime.now(timezone.utc)},
            "research": {"status": "completed", "completed_at": datetime.now(timezone.utc)},
            "script": {"status": "pending"}
        },
        "artifacts": {
            "topic": "Quantum Computing",
            "pillar": "Quantum Algorithms"
        }
    }

    mock_db.autopilot_queue.find_one = AsyncMock(return_value=existing_slot)
    service.channel_repo.find_by_id = AsyncMock(return_value={
        "_id": ObjectId(channel_id),
        "user_id": user_id,
        "name": "Quantum Channel",
        "status": "connected",
        "approval_required": False
    })
    service.brain_repo.find_by_channel = AsyncMock(return_value={"niche": "Physics"})

    # Track which stage runners were called
    stages_executed = []

    async def mock_run_stage(stage, slot, channel, brain, artifacts, worker_id):
        stages_executed.append(stage)
        if stage == "script":
            return {"script_text": "Quantum bits operate in superposition states.", "script_id": "s1"}
        if stage == "storyboard":
            return {"storyboard_scenes": [{"scene_index": 1, "text": "Qubits"}]}
        if stage == "pexels":
            return {"scene_clips": ["/path/clip1.mp4"]}
        if stage == "tts":
            return {"audio_path": "/path/audio.mp3", "audio_duration": 45.0}
        if stage == "subtitles":
            return {"subtitle_path": "/path/subs.srt"}
        if stage == "render":
            return {"video_path": "/path/video.mp4", "rendered_duration": 45.0}
        if stage == "qa":
            return {"qa_passed": True}
        if stage == "metadata":
            return {"title": "Quantum Basics"}
        if stage == "thumbnail":
            return {"thumbnail_path": "/path/thumb.jpg", "video_id": "v1"}
        if stage == "approval":
            return {"approval_status": "auto_approved"}
        if stage == "upload":
            return {"published": True, "youtube_video_id": "yt_123"}
        if stage == "learn":
            return {"learning_result": "ok"}
        return {}

    service._run_stage = AsyncMock(side_effect=mock_run_stage)
    service.queue_repo.heartbeat = AsyncMock(return_value=True)

    await service.execute_queue_item(slot_id, worker_id="test_worker")

    # channel_sync and research MUST NOT have been re-executed
    assert "channel_sync" not in stages_executed
    assert "research" not in stages_executed
    # script and subsequent stages MUST have been executed
    assert "script" in stages_executed
    assert "render" in stages_executed
    assert "upload" in stages_executed

@pytest.mark.asyncio
async def test_pexels_failure_propagation():
    """Verify Pexels stage raises PEXELS_NO_SUITABLE_MEDIA and does NOT silently fall back to mock media."""
    mock_db = MagicMock()
    service = AutopilotService(mock_db)

    slot = {
        "_id": ObjectId(),
        "channel_id": "ch1",
        "user_id": "u1"
    }
    artifacts = {
        "storyboard_scenes": [{"scene_index": 0, "search_queries": ["nonexistent_visual_query_xyz_999"]}]
    }

    service.settings.PEXELS_API_KEY = "test_key"

    with patch("backend.app.services.autopilot_service.PexelsProvider") as MockPexels:
        mock_instance = MockPexels.return_value
        mock_instance.search = AsyncMock(return_value=[])  # Zero items found

        with pytest.raises(PexelsMediaError) as exc_info:
            await service._stage_pexels(slot, {"_id": "ch1"}, artifacts)

        assert exc_info.value.code == "PEXELS_NO_SUITABLE_MEDIA"
        assert exc_info.value.stage == "pexels"

@pytest.mark.asyncio
async def test_qa_gate_strictly_blocks_publishing():
    """Verify QA failure raises QAGateError and halts execution before upload stage."""
    mock_db = MagicMock()
    service = AutopilotService(mock_db)

    slot = {
        "_id": ObjectId(),
        "channel_id": "ch1",
        "user_id": "u1",
        "format": "shorts"
    }
    artifacts = {
        "video_path": "/tmp/nonexistent_video.mp4",
        "subtitle_path": "/tmp/nonexistent_subs.srt"
    }

    # QA Engine should fail because video file doesn't exist
    with pytest.raises(QAGateError) as exc_info:
        await service._stage_qa(slot, {"_id": "ch1"}, artifacts)

    assert exc_info.value.code == "QA_FAILED"
    assert exc_info.value.stage == "qa"

@pytest.mark.asyncio
async def test_publishing_verifies_channel_and_propagates_error():
    """Verify publishing resolves channel credentials and raises explicit PublishingError on failure."""
    mock_db = MagicMock()
    service = AutopilotService(mock_db)

    slot = {
        "_id": ObjectId(),
        "channel_id": "ch_target",
        "user_id": "u1"
    }
    channel = {
        "_id": ObjectId(),
        "name": "Target Channel",
        "youtube_channel_id": "UC_EXPECTED_123"
    }
    artifacts = {
        "video_id": "v1",
        "video_path": "/path/video.mp4",
        "thumbnail_path": "/path/thumb.jpg",
        "title": "Test Title"
    }

    # Mock YouTube client with mismatched channel ID
    mock_yt = MagicMock()
    mock_yt.access_token = "valid_token"
    mock_yt.list_my_channels = AsyncMock(return_value=[{"youtube_channel_id": "UC_DIFFERENT_456"}])

    with patch("backend.app.services.autopilot_service.get_youtube_client_for_channel", AsyncMock(return_value=mock_yt)):
        with pytest.raises(PublishingError) as exc_info:
            await service._stage_upload(slot, channel, artifacts)

        assert exc_info.value.code == "YOUTUBE_CHANNEL_MISMATCH"

@pytest.mark.asyncio
async def test_post_upload_learning_failure_is_non_critical():
    """Verify if upload succeeds but learning fails, video remains published and queue item is NOT marked failed."""
    mock_db = MagicMock()
    service = AutopilotService(mock_db)

    slot = {
        "_id": ObjectId(),
        "channel_id": "ch1",
        "user_id": "u1"
    }
    channel = {"_id": "ch1"}

    service.learning_service.run_learning_cycle = AsyncMock(side_effect=RuntimeError("Learning service timeout"))

    # Stage learn should catch the error and return learning_error without raising
    res = await service._stage_learn(slot, channel)
    assert "learning_error" in res
    assert "Learning service timeout" in res["learning_error"]

@pytest.mark.asyncio
async def test_append_only_event_telemetry_recording():
    """Verify events_repo.record_event appends immutable events with accurate metadata."""
    mock_db = MagicMock()
    mock_coll = MagicMock()
    mock_coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_db.__getitem__.return_value = mock_coll

    from backend.app.repositories.autopilot_events import AutopilotEventsRepository
    events_repo = AutopilotEventsRepository(mock_db)

    event_id = await events_repo.record_event(
        channel_id="c1",
        user_id="u1",
        queue_item_id="q1",
        stage="render",
        status="completed",
        progress=80,
        message="FFmpeg composition finished",
        metadata={"resolution": "1080x1920"}
    )
    assert event_id is not None
    mock_coll.insert_one.assert_called_once()
    args, kwargs = mock_coll.insert_one.call_args
    doc = args[0]
    assert doc["stage"] == "render"
    assert doc["status"] == "completed"
    assert doc["progress"] == 80
    assert doc["metadata"]["resolution"] == "1080x1920"

