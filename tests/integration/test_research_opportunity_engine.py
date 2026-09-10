import pytest
from unittest.mock import patch
from backend.app.database import db_manager
from backend.app.services.channel_service import ChannelService
from backend.app.services.research_service import ResearchService
from backend.app.models.content import ResearchOpportunity

@pytest.mark.asyncio
async def test_research_opportunity_generation_with_channel_brain():
    await db_manager.connect()
    db = db_manager.get_database()
    channel_service = ChannelService(db)

    user_id = "user_research_test"
    channel_id = None

    try:
        # Create test channel
        ch = await channel_service.create_channel(user_id, {
            "name": "Space Exploration",
            "description": "Space science and astronomy shorts"
        })
        channel_id = ch["id"]

        # Directly insert a ChannelBrain for this channel to test opportunity grounding
        await db.channel_brains.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {"$set": {
                "channel_id": channel_id,
                "user_id": user_id,
                "niche": "Space & Astronomy",
                "target_audience": "Space enthusiasts and students",
                "positioning": "Fast-paced, verifiable cosmic mysteries",
                "content_pillars": [
                    {"name": "James Webb Discoveries", "description": "New JWST findings", "target_ratio": 0.5},
                    {"name": "Black Holes", "description": "Astrophysics mysteries", "target_ratio": 0.5}
                ],
                "winning_hooks": [
                    {"hook_type": "shocking_fact", "pattern": "Astronomers just spotted something that shouldn't exist...", "effectiveness_score": 0.9}
                ],
                "learned_rules": ["Highlight the scale of distance in the first 5 seconds"],
                "strategy_version": 1
            }},
            upsert=True
        )

        # Mock AI Gateway's _chat_json to test deterministically without 3-minute local LLM wait
        mock_ai_opportunities = [
            {
                "topic": "The Impossible Galaxy Found by James Webb",
                "content_pillar": "James Webb Discoveries",
                "why_now": "New Nature paper published this week",
                "evidence": "JWST spectroscopy data reveals massive early galaxy",
                "content_gap": "Mainstream news missed how this challenges Big Bang timelines",
                "recommended_angle": "Explain the crisis in cosmology in 45 seconds",
                "target_audience": "Space enthusiasts",
                "hooks": ["Astronomers just spotted a galaxy that breaks physics..."],
                "sources": ["Nature Astronomy 2026", "NASA Webb Team"],
                "opportunity_score": 94.0,
                "confidence": 0.92
            },
            {
                "topic": "What Actually Happens at the Center of a Black Hole",
                "content_pillar": "Black Holes",
                "why_now": "Viral debate following new singularity paper",
                "evidence": "Trending search term on YouTube Shorts",
                "content_gap": "Most videos use outdated artist impressions without spacetime physics",
                "recommended_angle": "Visual time-dilation simulation",
                "hooks": ["Time literally stops here, but not how you think..."],
                "sources": ["Physical Review Letters"],
                "opportunity_score": 89.5,
                "confidence": 0.88
            }
        ]

        from backend.app.ai.gateway import AIGateway
        from backend.app.config import get_settings

        ai_gw = AIGateway(get_settings())

        with patch.object(ai_gw, "_chat_json", return_value=mock_ai_opportunities):
            research_service = ResearchService(db, ai_gw)

            # Generate opportunities
            opps = await research_service.generate_channel_opportunities(user_id, channel_id, count=2)

            assert len(opps) == 2
            assert opps[0]["topic"] == "The Impossible Galaxy Found by James Webb"
            assert opps[0]["content_pillar"] == "James Webb Discoveries"
            assert opps[0]["opportunity_score"] == 94.0
            assert opps[1]["topic"] == "What Actually Happens at the Center of a Black Hole"

            # Verify persisted in database
            stored_reports = await research_service.list_research(user_id, channel_id)
            assert len(stored_reports) >= 2
            topics = [r["topic"] for r in stored_reports]
            assert "The Impossible Galaxy Found by James Webb" in topics

    finally:
        if channel_id:
            await db.channels.delete_one({"_id": channel_id})
            await db.channel_brains.delete_many({"channel_id": channel_id})
            await db.research_reports.delete_many({"channel_id": channel_id})
        await db_manager.disconnect()

