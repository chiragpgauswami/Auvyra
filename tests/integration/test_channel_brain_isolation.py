import pytest
from backend.app.database import db_manager
from backend.app.services.channel_service import ChannelService

@pytest.mark.asyncio
async def test_channel_brain_creation_and_isolation():
    await db_manager.connect()
    db = db_manager.get_database()
    service = ChannelService(db)

    user1_id = "user_brain_test_1"
    user2_id = "user_brain_test_2"

    # Clean up test documents
    await db.channels.delete_many({"user_id": {"$in": [user1_id, user2_id]}})
    await db.channel_brains.delete_many({"user_id": {"$in": [user1_id, user2_id]}})

    try:
        # Create Channel A for User 1
        ch_a = await service.create_channel(user1_id, {
            "name": "Finance Alpha",
            "description": "Personal finance and investing shorts"
        })
        channel_a_id = ch_a["id"]

        # Create Channel B for User 1
        ch_b = await service.create_channel(user1_id, {
            "name": "Tech Matrix",
            "description": "Future tech and AI breakdowns"
        })
        channel_b_id = ch_b["id"]

        # Create Channel C for User 2 (different tenant)
        ch_c = await service.create_channel(user2_id, {
            "name": "Cooking Masters",
            "description": "Quick culinary shorts"
        })
        channel_c_id = ch_c["id"]

        # 1. Onboard Channel A
        onboard_a_payload = {
            "niche": "Personal Finance",
            "target_audience": "Millennials looking to invest",
            "tone": "informative",
            "content_pillars": ["Index Funds", "Real Estate", "Budgeting"]
        }
        brain_a = await service.onboard_channel(user1_id, channel_a_id, onboard_a_payload)
        assert brain_a["channel_id"] == channel_a_id
        assert brain_a["user_id"] == user1_id
        assert brain_a["niche"] == "Personal Finance"
        assert len(brain_a["content_pillars"]) >= 1

        # 2. Onboard Channel B
        onboard_b_payload = {
            "niche": "Artificial Intelligence",
            "target_audience": "Software engineers and tech enthusiasts",
            "tone": "provocative",
            "content_pillars": ["LLMs", "Robotics", "Quantum Computing"]
        }
        brain_b = await service.onboard_channel(user1_id, channel_b_id, onboard_b_payload)
        assert brain_b["channel_id"] == channel_b_id
        assert brain_b["user_id"] == user1_id
        assert brain_b["niche"] == "Artificial Intelligence"

        # 3. Verify Isolation between Channel A and Channel B
        fetched_brain_a = await service.get_brain(user1_id, channel_a_id)
        fetched_brain_b = await service.get_brain(user1_id, channel_b_id)

        assert fetched_brain_a["niche"] == "Personal Finance"
        assert fetched_brain_b["niche"] == "Artificial Intelligence"
        assert fetched_brain_a["channel_id"] != fetched_brain_b["channel_id"]

        # 4. Verify Cross-Tenant Isolation: User 2 cannot access User 1's Channel A brain
        cross_tenant_brain = await service.get_brain(user2_id, channel_a_id)
        assert cross_tenant_brain is None

        # 5. Verify Brain Rebuild increments strategy version
        assert fetched_brain_a["strategy_version"] == 1
        rebuilt_a = await service.rebuild_brain(user1_id, channel_a_id)
        assert rebuilt_a["strategy_version"] == 2
        assert rebuilt_a["channel_id"] == channel_a_id

    finally:
        # Clean up
        await db.channels.delete_many({"user_id": {"$in": [user1_id, user2_id]}})
        await db.channel_brains.delete_many({"user_id": {"$in": [user1_id, user2_id]}})
        await db_manager.disconnect()
