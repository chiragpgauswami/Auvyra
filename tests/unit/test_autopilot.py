import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.autopilot_service import AutopilotService
from backend.app.models.metadata import VideoMetadataPackage
from backend.app.video.models import VideoGenerationResult

@pytest.mark.asyncio
async def test_toggle_autopilot():
    mock_db = MagicMock()
    service = AutopilotService(mock_db)

    service.channel_repo.find_by_id = AsyncMock(return_value={
        "_id": "chan_1",
        "user_id": "u1",
        "autopilot_enabled": False,
        "approval_required": True
    })
    service.channel_repo.update_one = AsyncMock(return_value=True)

    res = await service.toggle_autopilot(user_id="u1", channel_id="chan_1", enabled=True, approval_required=False)
    assert res["autopilot_enabled"] is True
    assert res["approval_required"] is False
    service.channel_repo.update_one.assert_called_once()

@pytest.mark.asyncio
async def test_run_autopilot_cycle_with_approval_gate():
    mock_db = MagicMock()
    mock_ai = MagicMock()
    service = AutopilotService(mock_db, mock_ai)

    # 1. Channel setup
    service.channel_repo.find_by_id = AsyncMock(return_value={
        "_id": "chan_100",
        "user_id": "u100",
        "name": "AI Explorers",
        "approval_required": True
    })

    # 2. Brain setup
    service.brain_repo.find_by_channel = AsyncMock(return_value={
        "niche": "AI Tech",
        "winning_hooks": ["Do not ignore this AI update."],
        "learned_rules": ["Keep transitions under 3s"]
    })

    # 3. Mock research opportunity
    service.research_service.generate_channel_opportunities = AsyncMock(return_value=[
        {
            "topic": "Autonomous Coding Agents in 2026",
            "opportunity_score": 94.0,
            "recommended_angle": "How AI writes and tests whole platforms."
        }
    ])

    # 4. Mock script generation
    service.content_service.generate_script = AsyncMock(return_value={
        "id": "script_100",
        "script_text": "Autonomous agents are transforming software engineering forever. Here is how."
    })

    # 5. Mock metadata generation
    service.metadata_service.generate_metadata = AsyncMock(return_value=VideoMetadataPackage(
        title="Autonomous Coding In 2026 Is Insane",
        description="Full breakdown of AI coding workflows.",
        tags=["ai", "coding", "software"],
        hashtags=["#ai", "#coding"],
        thumbnail_text_overlay="AI WRITES EVERYTHING"
    ))

    # 6. Mock video generation
    service.video_generation_service.generate = AsyncMock(return_value=VideoGenerationResult(
        video_path="media/videos/chan_100/video_100.mp4",
        duration=45.2,
        width=1080,
        height=1920,
        size_bytes=15000000
    ))

    # 7. Mock thumbnail generation
    service.thumbnail_service.generate_thumbnail = MagicMock(return_value="media/thumbnails/thumb_100.jpg")

    # 8. Mock DB insertions
    service.video_repo.insert_one = AsyncMock(return_value="vid_doc_100")
    service.notification_repo.create_notification = AsyncMock(return_value="notif_100")
    service.learning_service.run_learning_cycle = AsyncMock(return_value={"status": "success"})

    # Run cycle
    result = await service.run_autopilot_cycle("u100", "chan_100")

    assert result["status"] == "completed"
    assert result["video_id"] == "vid_doc_100"
    assert result["title"] == "Autonomous Coding In 2026 Is Insane"
    assert result["approval_required"] is True
    # Verify approval notification was queued
    service.notification_repo.create_notification.assert_called_once()
    # Verify video was registered
    service.video_repo.insert_one.assert_called_once()
    # Verify learning cycle was triggered
    service.learning_service.run_learning_cycle.assert_called_once_with("u100", "chan_100")
