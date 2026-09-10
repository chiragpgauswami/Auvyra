import pytest
from datetime import datetime, timezone
from backend.app.services.learning_service import LearningService
from backend.app.services.analytics_service import AnalyticsService
from backend.app.repositories.channels import ChannelRepository, ChannelMemoryRepository
from backend.app.repositories.analytics import AnalyticsRepository
from tests.fixtures.sample_data import SAMPLE_USER_A

@pytest.mark.asyncio
async def test_learning_loop_real_data(test_db):
    user_repo = test_db["users"]
    user_doc = {
        "email": SAMPLE_USER_A["email"],
        "name": SAMPLE_USER_A["name"],
        "password_hash": "hash123",
        "created_at": datetime.now(timezone.utc)
    }
    res = await user_repo.insert_one(user_doc)
    user_id = str(res.inserted_id)

    ch_repo = ChannelRepository(test_db)
    channel_id = await ch_repo.insert_one({
        "user_id": user_id,
        "name": "Learning Test Channel",
        "description": "Channel for testing real learning loop",
        "status": "connected"
    })

    analytics_service = AnalyticsService(test_db)
    learning_service = LearningService(test_db)

    # 1. Before any snapshots, generating insights returns empty list (zero fake data)
    empty_insights = await analytics_service.generate_insights(user_id, channel_id)
    assert empty_insights == []

    # 2. Add real analytics snapshots
    await analytics_service.create_snapshot(user_id, {
        "channel_id": channel_id,
        "views": 1500,
        "likes": 120,
        "comments": 35,
        "shares": 15,
        "watch_time_hours": 42.5,
        "ctr": 5.4,
        "avg_view_duration": 48.0
    })
    await analytics_service.create_snapshot(user_id, {
        "channel_id": channel_id,
        "views": 2500,
        "likes": 210,
        "comments": 65,
        "shares": 30,
        "watch_time_hours": 75.0,
        "ctr": 6.8,
        "avg_view_duration": 52.0
    })

    # 3. Generate insights from real snapshots
    insights = await analytics_service.generate_insights(user_id, channel_id)
    assert len(insights) >= 1
    insight = insights[0]
    # Verify metrics are calculated strictly from real data (1500 + 2500 = 4000 total views)
    assert insight["supporting_metrics"]["total_views"] == 4000
    assert insight["supporting_metrics"]["sample_size"] == 2
    assert insight["supporting_metrics"]["avg_views"] == 2000.0

    # 4. Trigger learning engine to update channel memory
    memory = await learning_service.update_channel_memory(user_id, channel_id)
    assert memory is not None
    assert memory["channel_id"] == channel_id
    assert "strategy_insights" in memory
    # Memory must contain real insight from real snapshots
    assert len(memory["strategy_insights"]) >= 1
    assert any(si.get("supporting_metrics", {}).get("total_views") == 4000 for si in memory["strategy_insights"])

    # Verify no fake hardcoded strings exist
    assert not any(t.get("topic") == "Practical AI Tools" and t.get("avg_retention") == 0.72 for t in memory.get("best_topics", []))
    assert not any(h.get("pattern") == "Stop doing X manually, use this new tool" for h in memory.get("best_hooks", []))

@pytest.mark.asyncio
async def test_channel_brain_closed_loop_feedback(test_db):
    user_repo = test_db["users"]
    user_res = await user_repo.insert_one({
        "email": "brain_learn@test.com",
        "name": "Brain Learner",
        "password_hash": "hash123",
        "created_at": datetime.now(timezone.utc)
    })
    user_id = str(user_res.inserted_id)

    ch_repo = ChannelRepository(test_db)
    channel_id = await ch_repo.insert_one({
        "user_id": user_id,
        "name": "Closed Loop Channel",
        "status": "connected"
    })

    # Initialize ChannelBrain
    from backend.app.repositories.brain import ChannelBrainRepository
    brain_repo = ChannelBrainRepository(test_db)
    await brain_repo.upsert_brain(channel_id, user_id, {
        "niche": "AI Tools",
        "winning_hooks": [],
        "learned_rules": [],
        "strategy_version": 1
    })

    # Create a script and video
    script_repo = test_db["scripts"]
    script_res = await script_repo.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "title": "5 Gamechanging AI Tools",
        "script_text": "Stop scrolling right now. These five tools will save you 20 hours a week.",
        "structured_data": {"selected_hook": "Stop scrolling right now. These five tools will save you 20 hours a week."},
        "created_at": datetime.now(timezone.utc)
    })
    script_id = str(script_res.inserted_id)

    vid_repo = test_db["videos"]
    vid_res = await vid_repo.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "title": "5 Gamechanging AI Tools",
        "script_id": script_id,
        "status": "published",
        "created_at": datetime.now(timezone.utc)
    })
    vid_id = str(vid_res.inserted_id)

    # Add a top-performing snapshot for this video
    analytics_repo = test_db["analytics_snapshots"]
    await analytics_repo.insert_one({
        "user_id": user_id,
        "channel_id": channel_id,
        "video_id": vid_id,
        "views": 50000,
        "likes": 4200,
        "watch_time_hours": 1200.0,
        "ctr": 8.5,
        "created_at": datetime.now(timezone.utc)
    })

    # Run closed-loop learning cycle
    learning_service = LearningService(test_db)
    cycle_result = await learning_service.run_learning_cycle(user_id, channel_id)

    assert cycle_result["status"] == "success"
    assert cycle_result["brain_version"] > 1

    # Verify ChannelBrain now holds the winning hook and synthesized rule!
    brain = await brain_repo.find_by_channel(channel_id, user_id)
    assert brain is not None
    assert len(brain.get("winning_hooks", [])) >= 1
    assert "Stop scrolling right now" in brain["winning_hooks"][0]
    assert len(brain.get("learned_rules", [])) >= 1
    assert any("5 Gamechanging AI Tools" in r or "retention" in r for r in brain["learned_rules"])
    assert "5 Gamechanging AI Tools" in brain.get("winning_topics", [])


