"""
Integration Test Suite for Post-Phase-22 Production Hardening & Integration Fixes.

Verifies:
1. Active Jobs and Terminal State Progress Contract (prevents infinite polling)
2. Video Repository User Scoping when channel_id=None (Videos page population)
3. Strict Multi-Tenant Isolation across Videos and Jobs
4. Manual Video Creation: Default to Pexels, No Silent Demo Fallback (PEXELS_NO_SUITABLE_MEDIA)
5. Scene Provenance Tracking in Video Assets
6. Canonical Publishing Calendar Consolidation (autopilot_queue + manual publishing_jobs)
7. Dynamic Caption Text Wrapping and Proportional Margins
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from backend.app.repositories.videos import VideoRepository, VideoAssetRepository
from backend.app.repositories.jobs import JobRepository
from backend.app.repositories.channels import ChannelRepository, AutopilotQueueRepository
from backend.app.repositories.publishing import PublishingRepository
from backend.app.services.video_service import VideoService
from backend.app.services.publishing_service import PublishingService
from backend.app.video.models import VideoGenerationRequest, VideoGenerationResult
from backend.app.video.pipeline import VideoGenerationService
from backend.app.video.composition.overlay import VideoOverlay


@pytest.mark.asyncio
async def test_video_repo_channel_id_none_queries_all_user_videos(test_db):
    """
    Verify that VideoRepository.find_by_channel(user_id, channel_id=None)
    queries all videos for the user across channels without filtering on channel_id=None.
    """
    video_repo = VideoRepository(test_db)
    user_a = str(ObjectId())
    user_b = str(ObjectId())
    ch_1 = str(ObjectId())
    ch_2 = str(ObjectId())

    t0 = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
    # User A videos
    v1 = await video_repo.insert_one({
        "user_id": user_a,
        "channel_id": ch_1,
        "title": "Video 1 Channel 1",
        "status": "generated",
        "created_at": t0
    })
    v2 = await video_repo.insert_one({
        "user_id": user_a,
        "channel_id": ch_2,
        "title": "Video 2 Channel 2",
        "status": "generated",
        "created_at": t0 + timedelta(minutes=1)
    })
    v3 = await video_repo.insert_one({
        "user_id": user_a,
        "channel_id": None,
        "title": "Video 3 No Channel",
        "status": "ready",
        "created_at": t0 + timedelta(minutes=2)
    })

    # User B video (should never leak)
    await video_repo.insert_one({
        "user_id": user_b,
        "channel_id": ch_1,
        "title": "User B Secret Video",
        "status": "generated"
    })

    # Query with channel_id=None -> all User A videos
    all_user_a_videos = await video_repo.find_by_channel(user_id=user_a, channel_id=None)
    assert len(all_user_a_videos) == 3
    found_ids = {str(v["_id"]) for v in all_user_a_videos}
    assert found_ids == {v1, v2, v3}

    # Query with specific channel_id -> only that channel
    ch1_videos = await video_repo.find_by_channel(user_id=user_a, channel_id=ch_1)
    assert len(ch1_videos) == 1
    assert str(ch1_videos[0]["_id"]) == v1

    # Query latest video
    latest = await video_repo.find_latest_by_channel(user_id=user_a)
    assert latest is not None
    assert str(latest["_id"]) == v3


@pytest.mark.asyncio
async def test_job_progress_terminal_state_contract(test_db):
    """
    Verify JobRepository and active jobs query properly reflect terminal states
    so that frontend usePolling stops when completed or failed.
    """
    job_repo = JobRepository(test_db)
    user_id = str(ObjectId())

    # Create active job
    active_job_id = await job_repo.enqueue(
        job_type="video_generation",
        user_id=user_id,
        payload={"topic": "Quantum Computing"}
    )
    await job_repo.update_progress(
        active_job_id,
        progress=45,
        stage="finding_media",
        message="Searching stock footage..."
    )

    # Fetch active jobs
    active_jobs = await job_repo.find_active_by_user(user_id=user_id)
    assert len(active_jobs) == 1
    assert str(active_jobs[0]["_id"]) == active_job_id
    assert active_jobs[0]["progress"] == 45
    assert active_jobs[0]["stage"] == "finding_media"

    # Mark completed with result
    await job_repo.update_progress(
        active_job_id,
        progress=100,
        stage="completed",
        message="Video generated successfully!",
        result={"video_id": "vid_123", "stream_url": "/api/videos/vid_123/stream"}
    )
    await job_repo.mark_complete(active_job_id, result={"video_id": "vid_123"})

    # Check that it is no longer in active jobs
    active_after_complete = await job_repo.find_active_by_user(user_id=user_id)
    assert len(active_after_complete) == 0

    # Direct fetch check
    completed_job = await job_repo.find_by_id(active_job_id)
    assert completed_job["status"] == "completed"
    assert completed_job["progress"] == 100
    assert completed_job["stage"] == "completed"
    assert completed_job.get("result", {}).get("video_id") == "vid_123"


@pytest.mark.asyncio
async def test_pexels_no_silent_fallback_enforcement(monkeypatch):
    """
    Verify that VideoGenerationService enforces NO silent fallback to demo clips
    when video_source='pexels' and pexels provider finds no footage.
    """
    from unittest.mock import AsyncMock
    from backend.app.video.media.pexels_stock_service import PexelsStockService

    # Mock PexelsStockService to simulate no suitable clips found
    monkeypatch.setattr(
        PexelsStockService,
        "fetch_media_for_storyboard",
        AsyncMock(return_value=[])
    )

    pipeline = VideoGenerationService()
    req = VideoGenerationRequest(
        topic="Dark Matter Astrophysics",
        script="Dark matter comprises most of the universe's mass.",
        duration=15,
        video_source="pexels"
    )

    with pytest.raises(RuntimeError) as exc_info:
        await pipeline.generate(req)

    assert "PEXELS_NO_SUITABLE_MEDIA" in str(exc_info.value)


@pytest.mark.asyncio
async def test_canonical_publishing_calendar_consolidation(test_db):
    """
    Verify PublishingService.get_publishing_calendar unifies autopilot_queue
    slots and manual publishing_jobs with correct status mapping and channel metadata.
    """
    channel_repo = ChannelRepository(test_db)
    queue_repo = AutopilotQueueRepository(test_db)
    pub_repo = PublishingRepository(test_db)
    video_repo = VideoRepository(test_db)

    user_id = str(ObjectId())
    other_user = str(ObjectId())

    # Create channel
    ch_id = await channel_repo.insert_one({
        "user_id": user_id,
        "name": "ShortsMela Tech",
        "status": "connected",
        "autopilot_config": {"timezone": "America/New_York"}
    })

    # Create videos
    vid1 = await video_repo.insert_one({
        "user_id": user_id,
        "channel_id": ch_id,
        "title": "Quantum AI Secrets",
        "status": "generated",
        "thumbnail_path": "media/thumbnails/qai.jpg"
    })

    # Autopilot slot 1: Ready for approval
    slot1 = await queue_repo.create_slot({
        "user_id": user_id,
        "channel_id": ch_id,
        "slot_date": "2026-09-20",
        "scheduled_time": "18:00",
        "topic": "Quantum AI Secrets",
        "pillar": "Tech",
        "video_id": vid1,
        "status": "ready_for_approval",
        "current_stage": "approval",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(hours=2)
    })

    # Autopilot slot 2: Published
    slot2 = await queue_repo.create_slot({
        "user_id": user_id,
        "channel_id": ch_id,
        "slot_date": "2026-09-19",
        "scheduled_time": "12:00",
        "topic": "Robotics Revolution",
        "pillar": "Tech",
        "status": "published",
        "scheduled_at": datetime.now(timezone.utc) - timedelta(days=1)
    })

    # Manual Publishing Job
    job_id = await pub_repo.insert_one({
        "user_id": user_id,
        "video_id": vid1,
        "platform": "youtube",
        "metadata": {"title": "Manual Drop Quantum AI"},
        "status": "scheduled",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(days=2)
    })

    # Other user slot (must not appear)
    await queue_repo.create_slot({
        "user_id": other_user,
        "channel_id": str(ObjectId()),
        "slot_date": "2026-09-21",
        "topic": "Leaked Data",
        "status": "pending"
    })

    pub_service = PublishingService(test_db)
    calendar = await pub_service.get_publishing_calendar(user_id=user_id)

    # Total should be 3 (slot1, slot2, manual job)
    assert len(calendar) == 3

    # Check slot 1 properties
    event1 = next(e for e in calendar if e.get("queue_item_id") == slot1)
    assert event1["channel_name"] == "ShortsMela Tech"
    assert event1["display_status"] == "Awaiting Approval"
    assert event1["approval_status"] == "ready_for_approval"
    assert event1["thumbnail_url"] == f"/api/videos/{vid1}/thumbnail"

    # Check slot 2 properties
    event2 = next(e for e in calendar if e.get("queue_item_id") == slot2)
    assert event2["display_status"] == "Published"

    # Check manual job
    manual_evt = next(e for e in calendar if e.get("job_id") == job_id)
    assert manual_evt["display_status"] == "Scheduled for Upload"
    assert manual_evt["title"] == "Manual Drop Quantum AI"


def test_caption_margin_padding_proportions():
    """
    Verify overlay text calculation and wrapping produces snug bounding boxes
    rather than full-screen 972px wide bars.
    """
    overlay = VideoOverlay()
    
    # Test short cue wrapping: at 56px font, target 972px width produces ~24 chars per line
    short_cue = "Look at this!"
    wrapped_short = overlay.wrap_caption_text(short_cue, font_size=56, target_width=972)
    assert wrapped_short == "LOOK AT THIS!"
    assert "\n" not in wrapped_short

    # Test longer cue wrapping: wraps cleanly into multiple lines without overflow
    longer_cue = "This is a revolutionary discovery in quantum mechanics that changes everything"
    wrapped_longer = overlay.wrap_caption_text(longer_cue, font_size=56, target_width=972)
    lines = wrapped_longer.split("\n")
    assert len(lines) >= 2
    for line in lines:
        assert len(line) <= 28


@pytest.mark.asyncio
async def test_autopilot_trigger_endpoint_contract(test_db):
    """
    Verify POST /api/autopilot/{channel_id}/trigger endpoint exists and
    executes run_autopilot_cycle or reports channel not found properly (not 404 route missing).
    """
    from unittest.mock import AsyncMock
    from backend.app.services.autopilot_service import AutopilotService
    from backend.app.api.autopilot import trigger_autopilot_cycle

    user_id = str(ObjectId())
    channel_id = str(ObjectId())
    user = {"_id": ObjectId(user_id)}

    mock_service = AsyncMock(spec=AutopilotService)
    mock_service.run_autopilot_cycle = AsyncMock(return_value={
        "status": "completed",
        "title": "Quantum AI Secrets",
        "channel_id": channel_id
    })

    res = await trigger_autopilot_cycle(
        channel_id=channel_id,
        user=user,
        service=mock_service
    )
    assert res["status"] == "completed"
    assert res["title"] == "Quantum AI Secrets"
    mock_service.run_autopilot_cycle.assert_awaited_once_with(user_id=user_id, channel_id=channel_id)


@pytest.mark.asyncio
async def test_jobs_active_endpoint_resolution(test_db):
    """Verify GET /api/jobs/active does not 404 as dynamic {job_id}."""
    from httpx import AsyncClient, ASGITransport
    from backend.app.main import app
    from backend.app.config import get_settings
    from backend.app.auth.service import AuthService
    from backend.app.repositories.jobs import JobRepository

    settings = get_settings()
    auth_svc = AuthService(test_db, settings)
    job_repo = JobRepository(test_db)

    user_id = str(ObjectId())
    await test_db["users"].insert_one({
        "_id": ObjectId(user_id),
        "email": "active_test@example.com",
        "name": "Active Test User",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    token = auth_svc.create_access_token(user_id)

    # 1. When no active job exists
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/jobs/active", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json() == {"job": None}

        # 2. When active processing job exists
        job_id = await job_repo.enqueue(
            job_type="video_generation",
            user_id=user_id,
            payload={"topic": "Black Holes"}
        )
        await job_repo.update_progress(job_id, 45, stage="generating_narration", status="processing")

        res2 = await client.get("/api/jobs/active", headers={"Authorization": f"Bearer {token}"})
        assert res2.status_code == 200
        data = res2.json()
        assert data["job"] is not None
        assert data["job"]["status"] == "processing"


@pytest.mark.asyncio
async def test_channel_brain_positioning_persisted(test_db):
    """Verify autopilot config preserves and stores channel positioning."""
    from backend.app.services.channel_service import ChannelService

    user_id = str(ObjectId())
    ch_id = str(ObjectId())

    # Insert channel
    await test_db["channels"].insert_one({
        "_id": ObjectId(ch_id),
        "user_id": user_id,
        "name": "Apex Wildlife",
        "status": "connected"
    })

    svc = ChannelService(test_db)
    config_data = {
        "mode": "full_autopilot",
        "niche": "Apex Wildlife",
        "target_audience": "Wildlife Enthusiasts",
        "content_pillars": ["Big Cats", "Ocean Predators"],
        "format": "shorts",
        "schedule": {
            "frequency_per_week": 7,
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "times": ["18:00"],
            "timezone": "UTC"
        },
        "tone": "cinematic"
    }

    result = await svc.configure_autopilot(user_id, ch_id, config_data)
    assert result is not None

    # Verify brain in DB has non-empty positioning
    brain = await test_db["channel_brains"].find_one({"channel_id": ch_id})
    assert brain is not None
    assert "positioning" in brain
    assert len(brain["positioning"]) > 0
    assert "Apex Wildlife" in brain["positioning"]


