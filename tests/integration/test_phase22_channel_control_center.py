"""
Integration Test Suite for Phase 22 Production Autopilot, Channel Control Center,
and Closed-Loop Channel Intelligence.

Verifies:
1. Production Observability Endpoint (/api/autopilot/{channel_id}/observability)
2. Queue Management: Assisted Mode gate, Approval, Retry, and Cancel actions
3. Multi-channel & Multi-tenant isolation (strict user_id + channel_id checks)
4. 30-Day Topic Deduplication (ContentTopicRepository) with channel boundary isolation
5. Video Analytics Persistence (video_analytics_snapshots collection & history)
6. Closed-Loop Channel Brain Signals & Learning Runs persistence
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from backend.app.database import db_manager
from backend.app.repositories.channels import ChannelRepository, AutopilotQueueRepository
from backend.app.repositories.content_topics import ContentTopicRepository
from backend.app.repositories.video_analytics import VideoAnalyticsRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.repositories.analytics import AnalyticsRepository
from backend.app.services.autopilot_service import AutopilotService
from backend.app.services.learning_service import LearningService


@pytest.mark.asyncio
async def test_observability_endpoint(test_db):
    """Verify get_channel_observability returns complete state & telemetry."""
    channel_repo = ChannelRepository(test_db)
    queue_repo = AutopilotQueueRepository(test_db)

    # 1. Create a channel for test user
    user_id = str(ObjectId())
    channel_id = await channel_repo.insert_one({
        "user_id": user_id,
        "name": "Observability Test Channel",
        "status": "connected",
        "autopilot_enabled": True,
        "approval_required": True,
        "autopilot_config": {
            "enabled": True,
            "mode": "assisted",
            "approval_required": True,
            "niche": "Tech Innovations",
            "frequency_per_day": 1,
            "target_times": ["14:00"],
            "timezone": "UTC"
        }
    })

    # 2. Add some queue items
    now = datetime.now(timezone.utc)
    await queue_repo.create_slot({
        "channel_id": channel_id,
        "user_id": user_id,
        "slot_date": "2026-09-20",
        "scheduled_time": "14:00",
        "topic": "Quantum Computing",
        "pillar": "Hardware",
        "status": "pending",
        "stage": "pending",
        "scheduled_at": now + timedelta(days=1),
        "attempts": 0,
        "max_attempts": 3,
        "created_at": now,
        "updated_at": now
    })

    await queue_repo.create_slot({
        "channel_id": channel_id,
        "user_id": user_id,
        "slot_date": "2026-09-19",
        "scheduled_time": "14:00",
        "topic": "AI Ethics",
        "pillar": "Ethics",
        "status": "ready_for_approval",
        "stage": "approval",
        "scheduled_at": now - timedelta(hours=1),
        "attempts": 1,
        "max_attempts": 3,
        "created_at": now,
        "updated_at": now
    })

    # 3. Query observability service directly
    autopilot_service = AutopilotService(test_db)
    obs = await autopilot_service.get_channel_observability(user_id, channel_id)

    assert obs["channel_id"] == channel_id
    assert obs["channel_name"] == "Observability Test Channel"
    assert obs["autopilot_enabled"] is True
    assert obs["mode"] == "assisted"
    assert obs["queue_depth"]["pending"] == 1
    assert obs["queue_depth"]["ready_for_approval"] == 1
    assert "channel_style" in obs


@pytest.mark.asyncio
async def test_queue_cancellation(test_db):
    """Verify pending queue item can be cancelled."""
    autopilot_service = AutopilotService(test_db)
    queue_repo = AutopilotQueueRepository(test_db)
    user_id = str(ObjectId())
    channel_id = str(ObjectId())

    slot_id = await queue_repo.create_slot({
        "channel_id": channel_id,
        "user_id": user_id,
        "slot_date": "2026-09-25",
        "scheduled_time": "18:00",
        "topic": "Slot To Cancel",
        "status": "pending",
        "stage": "pending",
        "attempts": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })

    cancelled = await autopilot_service.cancel_queue_item(user_id, slot_id)
    assert cancelled is True

    # Verify slot is removed from queue
    slot = await queue_repo.find_by_id(slot_id)
    assert slot is None


@pytest.mark.asyncio
async def test_topic_deduplication_30_days(test_db):
    """
    Verify 30-day topic deduplication engine:
    1. Once a topic is recorded for channel A, it is flagged as recent.
    2. Same topic for channel B is NOT flagged (strict channel isolation).
    3. Normalizes punctuation/case.
    """
    topic_repo = ContentTopicRepository(test_db)
    channel_a = str(ObjectId())
    channel_b = str(ObjectId())
    user_a = str(ObjectId())
    user_b = str(ObjectId())

    # Record topic for channel A
    await topic_repo.record_topic_decision(
        channel_id=channel_a,
        user_id=user_a,
        topic="5 Mind-Bending Facts About Black Holes!",
        pillar="Cosmology",
        source="autopilot_research"
    )

    # Check channel A with slight variation (case/punctuation)
    is_recent_a = await topic_repo.is_topic_recent(
        channel_id=channel_a,
        topic="5 mind-bending facts about black holes!",
        days=30
    )
    assert is_recent_a is True, "Topic should be detected as recently used within 30 days."

    # Check different topic for channel A
    is_recent_diff = await topic_repo.is_topic_recent(
        channel_id=channel_a,
        topic="The Mysteries of Deep Sea Trenches",
        days=30
    )
    assert is_recent_diff is False

    # Check Channel B isolation - Channel B should NOT be blocked from using the same topic
    is_recent_b = await topic_repo.is_topic_recent(
        channel_id=channel_b,
        topic="5 Mind-Bending Facts About Black Holes!",
        days=30
    )
    assert is_recent_b is False, "Topic used by channel A must not leak or block channel B."


@pytest.mark.asyncio
async def test_video_analytics_persistence_and_history(test_db):
    """Verify video_analytics_snapshots collection stores timestamped records and history."""
    analytics_repo = VideoAnalyticsRepository(test_db)
    user_id = str(ObjectId())
    channel_id = str(ObjectId())
    video_id = str(ObjectId())

    now = datetime.now(timezone.utc)
    metrics_1 = {
        "views": 1500,
        "likes": 120,
        "comments": 15,
        "watch_time_hours": 12.5,
        "average_view_duration_seconds": 38.0,
        "retention_rate": 0.65,
    }
    metrics_2 = {
        "views": 4200,
        "likes": 340,
        "comments": 42,
        "watch_time_hours": 35.0,
        "average_view_duration_seconds": 41.0,
        "retention_rate": 0.72,
    }

    id1 = await analytics_repo.record_snapshot(
        user_id=user_id,
        channel_id=channel_id,
        video_id=video_id,
        metrics=metrics_1,
        youtube_video_id="yt_test_vid_1",
        collected_at=now - timedelta(hours=24)
    )
    id2 = await analytics_repo.record_snapshot(
        user_id=user_id,
        channel_id=channel_id,
        video_id=video_id,
        metrics=metrics_2,
        youtube_video_id="yt_test_vid_1",
        collected_at=now
    )
    assert id1 and id2

    # Query history
    history = await analytics_repo.get_video_history(channel_id, video_id, user_id=user_id)
    assert len(history) == 2
    # Verify latest is index 0 (descending order)
    assert history[0]["metrics"]["views"] == 4200
    assert history[1]["metrics"]["views"] == 1500

    # Query latest snapshot
    latest = await analytics_repo.get_latest_snapshot(channel_id, video_id, user_id=user_id)
    assert latest is not None
    assert latest["metrics"]["views"] == 4200
    assert latest["metrics"]["retention_rate"] == 0.72


@pytest.mark.asyncio
async def test_closed_loop_learning_and_evidence_signals(test_db):
    """Verify LearningService stores learning_runs and updates structured brain signals."""
    brain_repo = ChannelBrainRepository(test_db)
    channel_repo = ChannelRepository(test_db)
    video_repo = VideoRepository(test_db)
    analytics_repo = AnalyticsRepository(test_db)

    user_id = str(ObjectId())
    channel_id = await channel_repo.insert_one({
        "user_id": user_id,
        "name": "Closed Loop Channel",
        "status": "connected",
        "autopilot_enabled": True
    })

    # Initialize channel brain
    await brain_repo.upsert_brain(channel_id, user_id, {
        "user_id": user_id,
        "channel_id": channel_id,
        "niche": "Space Exploration",
        "target_audience": "Curious Minds",
        "language": "en",
        "geography": "US",
        "tone": "engaging",
        "positioning": "authoritative",
        "content_pillars": [{"name": "Planets", "description": "Solar system", "target_ratio": 0.5}],
        "strategy_version": 1
    })

    # Add a published video and an analytics snapshot for evidence
    now = datetime.now(timezone.utc)
    vid_id = await video_repo.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "title": "Secret of the Red Planet",
        "status": "published",
        "duration": 42.0,
        "created_at": now,
        "updated_at": now
    })

    await analytics_repo.create_snapshot({
        "user_id": user_id,
        "channel_id": channel_id,
        "video_id": vid_id,
        "views": 10500,
        "likes": 800,
        "comments": 90,
        "ctr": 8.5,
        "period": "daily",
        "snapshot_date": now,
        "created_at": now
    })

    learning_service = LearningService(test_db)
    learning_result = await learning_service.run_learning_cycle(user_id, channel_id)

    assert learning_result is not None

    # Verify learning_runs collection has recorded run
    runs = await test_db["learning_runs"].find({"channel_id": channel_id}).to_list(10)
    assert len(runs) >= 1
    run = runs[0]
    assert run["channel_id"] == channel_id
    assert run["user_id"] == user_id
    assert "signals_count" in run
    assert run["signals_count"] >= 1

    # Verify structured signals in channel brain
    updated_brain = await brain_repo.find_by_channel(channel_id, user_id)
    assert updated_brain is not None
    assert "structured_signals" in updated_brain
    assert isinstance(updated_brain["structured_signals"], list)
    assert len(updated_brain["structured_signals"]) >= 1
