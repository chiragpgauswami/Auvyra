import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId

from backend.app.main import app
from backend.app.database import db_manager


@pytest.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_api_niche_recommendations_caching(test_db, api_client):
    """Verify niche recommendation retrieval, MongoDB caching, and refresh invalidation."""
    db = db_manager.get_database()

    # 1. Register User & Create Channel
    reg = await api_client.post("/api/auth/register", json={
        "email": "niche_tester@example.com",
        "password": "Password123!Secure",
        "name": "Niche Tester"
    })
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch_res = await api_client.post("/api/channels/", json={
        "name": "Tech Breakdown Daily",
        "description": "Short-form AI and coding insights"
    }, headers=headers)
    assert ch_res.status_code == 201
    channel_id = ch_res.json()["id"]

    # 2. Fetch Niches (First time - caches in DB)
    res1 = await api_client.get(f"/api/channels/{channel_id}/autopilot/niches?refresh=false", headers=headers)
    assert res1.status_code == 200
    niches1 = res1.json()
    assert len(niches1) >= 1
    assert "name" in niches1[0]
    assert "source" in niches1[0]
    assert "confidence" in niches1[0]
    assert "opportunity_score" in niches1[0]

    # Verify cached in MongoDB
    cache_doc = await db.niche_recommendations_cache.find_one({"channel_id": channel_id})
    assert cache_doc is not None
    assert len(cache_doc["recommendations"]) == len(niches1)

    # 3. Fetch Niches again (Served from cache)
    res2 = await api_client.get(f"/api/channels/{channel_id}/autopilot/niches?refresh=false", headers=headers)
    assert res2.status_code == 200
    niches2 = res2.json()
    assert niches2 == niches1

    # 4. Fetch with refresh=true
    res3 = await api_client.get(f"/api/channels/{channel_id}/autopilot/niches?refresh=true", headers=headers)
    assert res3.status_code == 200
    niches3 = res3.json()
    assert len(niches3) >= 1


@pytest.mark.asyncio
async def test_api_autopilot_configure_full_flow(test_db, api_client):
    """Verify full 8-step wizard configuration, persistent queue creation, brain update, and cache invalidation."""
    db = db_manager.get_database()

    # 1. Register User & Create Channel
    reg = await api_client.post("/api/auth/register", json={
        "email": "wizard_full_flow@example.com",
        "password": "Password123!Secure",
        "name": "Wizard Tester"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch_res = await api_client.post("/api/channels/", json={
        "name": "CloudArchitect",
        "description": "Cloud systems and DevOps"
    }, headers=headers)
    channel_id = ch_res.json()["id"]

    # Prime cache first
    await api_client.get(f"/api/channels/{channel_id}/autopilot/niches", headers=headers)
    cached_before = await db.niche_recommendations_cache.find_one({"channel_id": channel_id})
    assert cached_before is not None

    # 2. Configure Autopilot with valid 8-step payload
    config_payload = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "Cloud Architecture & DevOps",
        "custom_niche": None,
        "target_audience": "DevOps engineers and backend developers",
        "tone": "authoritative yet accessible",
        "language": "en",
        "target_geography": "US",
        "content_pillars": ["AWS Secrets", "Kubernetes Pitfalls", "Microservices Design"],
        "schedule": {
            "frequency_per_week": 3,
            "timezone": "America/New_York",
            "days_of_week": [0, 2, 4],  # Mon, Wed, Fri
            "times": ["09:00", "18:00"]
        },
        "approval_required": True,
        "privacy_status": "private",
        "tags": ["cloud", "devops", "aws", "docker"]
    }

    resp = await api_client.post(
        f"/api/channels/{channel_id}/autopilot/configure",
        json=config_payload,
        headers=headers
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "success"
    assert res_data["channel_id"] == channel_id
    assert res_data["config_version"] == 1
    assert res_data["autopilot_mode"] == "full_autopilot"
    assert res_data["scheduled_slots_count"] == 3

    # Verify Channel document in MongoDB
    chan_doc = await db.channels.find_one({"_id": ObjectId(channel_id)})
    assert chan_doc["autopilot_enabled"] is True
    assert chan_doc["approval_required"] is True
    assert chan_doc["autopilot_config"]["niche"] == "Cloud Architecture & DevOps"
    assert chan_doc["autopilot_config"]["schedule"]["timezone"] == "America/New_York"
    assert chan_doc["autopilot_config"]["config_version"] == 1

    # Verify structured Channel Brain
    brain_doc = await db.channel_brains.find_one({"channel_id": channel_id})
    assert brain_doc is not None
    assert brain_doc["niche"] == "Cloud Architecture & DevOps"
    assert brain_doc["target_audience"] == "DevOps engineers and backend developers"
    assert len(brain_doc["content_pillars"]) == 3
    assert brain_doc["publishing_strategy"]["frequency_per_week"] == 3
    assert brain_doc["publishing_strategy"]["timezone"] == "America/New_York"

    # Verify persistent Autopilot Queue in MongoDB
    queue_slots = await db.autopilot_queue.find({"channel_id": channel_id}).to_list(100)
    assert len(queue_slots) == 3
    for slot in queue_slots:
        assert slot["status"] == "pending"
        assert slot["timezone"] == "America/New_York"
        assert slot["scheduled_at"] is not None
        assert slot["format"] == "shorts"
        assert slot["pillar"] in ["AWS Secrets", "Kubernetes Pitfalls", "Microservices Design"]

    # Verify niche recommendations cache was invalidated on reconfiguration
    cached_after = await db.niche_recommendations_cache.find_one({"channel_id": channel_id})
    assert cached_after is None


@pytest.mark.asyncio
async def test_api_autopilot_configure_idempotency(test_db, api_client):
    """Verify configuring repeatedly does not create duplicate schedule slots."""
    db = db_manager.get_database()

    reg = await api_client.post("/api/auth/register", json={
        "email": "idempotent_tester@example.com",
        "password": "Password123!Secure",
        "name": "Idempotent Tester"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch_res = await api_client.post("/api/channels/", json={
        "name": "DataPipelines",
        "description": "Data engineering"
    }, headers=headers)
    channel_id = ch_res.json()["id"]

    config_payload = {
        "mode": "assisted",
        "format": "shorts",
        "niche": "Data Engineering",
        "schedule": {
            "frequency_per_week": 2,
            "timezone": "UTC",
            "days_of_week": [1, 3],
            "times": ["12:00"]
        },
        "content_pillars": ["SQL", "Kafka"]
    }

    # First configure
    res1 = await api_client.post(f"/api/channels/{channel_id}/autopilot/configure", json=config_payload, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["scheduled_slots_count"] == 2

    count_first = await db.autopilot_queue.count_documents({"channel_id": channel_id})
    assert count_first == 2

    # Re-run same configure
    res2 = await api_client.post(f"/api/channels/{channel_id}/autopilot/configure", json=config_payload, headers=headers)
    assert res2.status_code == 200
    # Because slots at the exact scheduled timestamps already exist, new created count should be 0
    assert res2.json()["scheduled_slots_count"] == 0

    count_second = await db.autopilot_queue.count_documents({"channel_id": channel_id})
    assert count_second == 2


@pytest.mark.asyncio
async def test_api_autopilot_mode_switch(test_db, api_client):
    """Verify switching between full_autopilot, assisted, and off is non-destructive and updates flags."""
    db = db_manager.get_database()

    reg = await api_client.post("/api/auth/register", json={
        "email": "modeswitch_tester@example.com",
        "password": "Password123!Secure",
        "name": "Mode Switcher"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch_res = await api_client.post("/api/channels/", json={
        "name": "FinanceDaily",
        "description": "Daily stock and market insights"
    }, headers=headers)
    channel_id = ch_res.json()["id"]

    base_payload = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "Finance",
        "schedule": {
            "frequency_per_week": 2,
            "timezone": "UTC",
            "days_of_week": [1, 4],
            "times": ["15:00"]
        },
        "content_pillars": ["Markets", "Real Estate"]
    }

    # 1. full_autopilot
    r1 = await api_client.post(f"/api/channels/{channel_id}/autopilot/configure", json=base_payload, headers=headers)
    assert r1.status_code == 200
    ch1 = await db.channels.find_one({"_id": ObjectId(channel_id)})
    assert ch1["autopilot_enabled"] is True
    assert ch1["autopilot_config"]["mode"] == "full_autopilot"

    # 2. assisted
    base_payload["mode"] = "assisted"
    r2 = await api_client.post(f"/api/channels/{channel_id}/autopilot/configure", json=base_payload, headers=headers)
    assert r2.status_code == 200
    ch2 = await db.channels.find_one({"_id": ObjectId(channel_id)})
    assert ch2["autopilot_enabled"] is True
    assert ch2["autopilot_config"]["mode"] == "assisted"

    # 3. off
    base_payload["mode"] = "off"
    r3 = await api_client.post(f"/api/channels/{channel_id}/autopilot/configure", json=base_payload, headers=headers)
    assert r3.status_code == 200
    ch3 = await db.channels.find_one({"_id": ObjectId(channel_id)})
    assert ch3["autopilot_enabled"] is False
    assert ch3["autopilot_config"]["mode"] == "off"

    # Verify previously generated slots are NOT wiped (non-destructive)
    slots = await db.autopilot_queue.find({"channel_id": channel_id}).to_list(10)
    assert len(slots) > 0


@pytest.mark.asyncio
async def test_api_cross_user_isolation(test_db, api_client):
    """Verify User B cannot access, configure, or read queues for User A's channel."""
    # User A
    reg_a = await api_client.post("/api/auth/register", json={
        "email": "user_a@example.com",
        "password": "Password123!Secure",
        "name": "User A"
    })
    token_a = reg_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    ch_a = await api_client.post("/api/channels/", json={"name": "Channel A"}, headers=headers_a)
    channel_a_id = ch_a.json()["id"]

    # User B
    reg_b = await api_client.post("/api/auth/register", json={
        "email": "user_b@example.com",
        "password": "Password123!Secure",
        "name": "User B"
    })
    token_b = reg_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B tries to get niches for Channel A
    r1 = await api_client.get(f"/api/channels/{channel_a_id}/autopilot/niches", headers=headers_b)
    assert r1.status_code == 404

    # User B tries to configure Channel A
    cfg_payload = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "Hacking",
        "schedule": {
            "frequency_per_week": 1,
            "timezone": "UTC",
            "days_of_week": [0],
            "times": ["10:00"]
        }
    }
    r2 = await api_client.post(f"/api/channels/{channel_a_id}/autopilot/configure", json=cfg_payload, headers=headers_b)
    assert r2.status_code == 404

    # User B tries to fetch config for Channel A
    r3 = await api_client.get(f"/api/channels/{channel_a_id}/autopilot/config", headers=headers_b)
    assert r3.status_code == 404

    # User B tries to fetch queue for Channel A
    r4 = await api_client.get(f"/api/channels/{channel_a_id}/autopilot/queue", headers=headers_b)
    assert r4.status_code == 404


@pytest.mark.asyncio
async def test_api_multi_channel_isolation(test_db, api_client):
    """Verify a single user with multiple channels maintains strict configuration and queue isolation."""
    db = db_manager.get_database()

    reg = await api_client.post("/api/auth/register", json={
        "email": "multichan_owner@example.com",
        "password": "Password123!Secure",
        "name": "Multi Channel Owner"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch1 = (await api_client.post("/api/channels/", json={"name": "Channel One"}, headers=headers)).json()
    ch2 = (await api_client.post("/api/channels/", json={"name": "Channel Two"}, headers=headers)).json()
    ch1_id = ch1["id"]
    ch2_id = ch2["id"]

    # Configure only Channel One
    cfg1 = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "Tech",
        "schedule": {
            "frequency_per_week": 2,
            "timezone": "UTC",
            "days_of_week": [1, 3],
            "times": ["10:00"]
        },
        "content_pillars": ["Hardware", "Software"]
    }
    await api_client.post(f"/api/channels/{ch1_id}/autopilot/configure", json=cfg1, headers=headers)

    # Check Channel 1 config & queue
    res1_cfg = await api_client.get(f"/api/channels/{ch1_id}/autopilot/config", headers=headers)
    assert res1_cfg.status_code == 200
    assert res1_cfg.json()["autopilot_enabled"] is True
    assert res1_cfg.json()["upcoming_queue_count"] == 2

    # Check Channel 2 remains unconfigured
    res2_cfg = await api_client.get(f"/api/channels/{ch2_id}/autopilot/config", headers=headers)
    assert res2_cfg.status_code == 200
    assert res2_cfg.json()["autopilot_enabled"] is False
    assert res2_cfg.json()["upcoming_queue_count"] == 0

    # Queue query for Channel 2 returns empty list
    res2_q = await api_client.get(f"/api/channels/{ch2_id}/autopilot/queue", headers=headers)
    assert res2_q.status_code == 200
    assert len(res2_q.json()) == 0


@pytest.mark.asyncio
async def test_api_get_queue_and_config_endpoints(test_db, api_client):
    """Verify GET /autopilot/config and GET /autopilot/queue return well-formed JSON payloads."""
    reg = await api_client.post("/api/auth/register", json={
        "email": "get_endpoints_tester@example.com",
        "password": "Password123!Secure",
        "name": "Endpoint Tester"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch = (await api_client.post("/api/channels/", json={"name": "History Bites"}, headers=headers)).json()
    ch_id = ch["id"]

    cfg = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "Ancient Rome",
        "schedule": {
            "frequency_per_week": 1,
            "timezone": "UTC",
            "days_of_week": [0],
            "times": ["11:00"]
        },
        "content_pillars": ["Legions"]
    }
    await api_client.post(f"/api/channels/{ch_id}/autopilot/configure", json=cfg, headers=headers)

    # Config endpoint
    conf_res = await api_client.get(f"/api/channels/{ch_id}/autopilot/config", headers=headers)
    assert conf_res.status_code == 200
    data = conf_res.json()
    assert data["channel_id"] == ch_id
    assert data["autopilot_enabled"] is True
    assert data["config"]["niche"] == "Ancient Rome"

    # Queue endpoint
    queue_res = await api_client.get(f"/api/channels/{ch_id}/autopilot/queue", headers=headers)
    assert queue_res.status_code == 200
    queue_items = queue_res.json()
    assert len(queue_items) == 1
    assert queue_items[0]["channel_id"] == ch_id
    assert queue_items[0]["pillar"] == "Legions"
    assert queue_items[0]["status"] == "pending"

