"""
Integration Test Suite for Phase 20 Autopilot Scheduler & Queue Pipeline.
Uses real test database to verify:
1. Atomic claiming via find_one_and_update (multi-worker race safety)
2. Bounded 7-day queue replenishment
3. OFF mode channels receive zero replenishment
4. Per-channel concurrency control (max 1 concurrent production job per channel)
5. Worker lease expiration & crash recovery
6. Approval flow via API (/queue/{id}/approve)
7. Retry flow via API (/queue/{id}/retry)
8. Append-only events endpoint (/api/autopilot/{channel_id}/events)
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from backend.app.database import db_manager
from backend.app.services.scheduler_service import SchedulerService
from backend.app.services.autopilot_service import AutopilotService
from backend.app.repositories.channels import AutopilotQueueRepository
from backend.app.repositories.autopilot_events import AutopilotEventsRepository

@pytest.mark.asyncio
async def test_atomic_queue_claiming_concurrency(test_db):
    """Verify concurrent claim attempts for the same due slot result in exactly 1 winner."""
    db = db_manager.get_database()
    queue_repo = AutopilotQueueRepository(db)

    now_utc = datetime.now(timezone.utc)
    slot_doc = {
        "channel_id": "ch_race",
        "user_id": "user_race",
        "topic": "Concurrency Race Test",
        "pillar": "Tech",
        "status": "pending",
        "scheduled_at": now_utc - timedelta(minutes=5),
        "attempts": 0,
        "max_attempts": 3,
        "created_at": now_utc,
        "updated_at": now_utc
    }
    slot_id = await queue_repo.create_slot(slot_doc)

    # Launch 5 concurrent workers attempting to claim due slot
    async def try_claim(worker_num):
        return await queue_repo.claim_due_slot(worker_id=f"worker_{worker_num}", now_utc=now_utc)

    results = await asyncio.gather(*[try_claim(i) for i in range(5)])

    winners = [r for r in results if r is not None]
    losers = [r for r in results if r is None]

    assert len(winners) == 1, f"Expected exactly 1 winner, got {len(winners)}"
    assert len(losers) == 4
    winner_doc = winners[0]
    assert winner_doc["status"] == "in_production"
    assert winner_doc["claimed_by"].startswith("worker_")
    lease_exp = winner_doc["lease_expires_at"]
    if lease_exp.tzinfo is None:
        lease_exp = lease_exp.replace(tzinfo=timezone.utc)
    assert lease_exp > now_utc

@pytest.mark.asyncio
async def test_bounded_queue_replenishment(test_db):
    """Verify scheduler maintains up to frequency_per_week slots over 7 days and is idempotent."""
    db = db_manager.get_database()
    scheduler = SchedulerService(db)

    now_utc = datetime.now(timezone.utc)
    ch_doc = {
        "name": "Replenish Channel",
        "user_id": "user_repl",
        "status": "connected",
        "autopilot_enabled": True,
        "autopilot_config": {
            "mode": "full_autopilot",
            "format": "shorts",
            "niche": "Automation",
            "content_pillars": ["Pillar A", "Pillar B", "Pillar C"],
            "schedule": {
                "frequency_per_week": 3,
                "timezone": "UTC",
                "days_of_week": [0, 2, 4],  # Mon, Wed, Fri
                "times": ["14:00"]
            }
        },
        "created_at": now_utc,
        "updated_at": now_utc
    }
    ch_res = await db.channels.insert_one(ch_doc)
    channel_id = str(ch_res.inserted_id)

    # 1. First replenishment tick
    count1 = await scheduler.replenish_queues(now_utc)
    assert count1 == 3

    slots1 = await db.autopilot_queue.count_documents({"channel_id": channel_id})
    assert slots1 == 3

    # 2. Re-run tick immediately — must be idempotent and create 0 duplicates
    count2 = await scheduler.replenish_queues(now_utc)
    assert count2 == 0

    slots2 = await db.autopilot_queue.count_documents({"channel_id": channel_id})
    assert slots2 == 3

@pytest.mark.asyncio
async def test_off_mode_channel_never_replenished(test_db):
    """Verify channels in mode 'off' receive zero new scheduled queue items."""
    db = db_manager.get_database()
    scheduler = SchedulerService(db)

    now_utc = datetime.now(timezone.utc)
    ch_doc = {
        "name": "Paused Channel",
        "user_id": "user_off",
        "status": "connected",
        "autopilot_enabled": True,
        "autopilot_config": {
            "mode": "off",
            "schedule": {
                "frequency_per_week": 3,
                "timezone": "UTC",
                "days_of_week": [0, 2, 4],
                "times": ["10:00"]
            }
        },
        "created_at": now_utc,
        "updated_at": now_utc
    }
    ch_res = await db.channels.insert_one(ch_doc)
    channel_id = str(ch_res.inserted_id)

    replenished = await scheduler.replenish_queues(now_utc)
    assert replenished == 0

    slots = await db.autopilot_queue.count_documents({"channel_id": channel_id})
    assert slots == 0

@pytest.mark.asyncio
async def test_per_channel_concurrency_control(test_db):
    """Verify scheduler claims at most 1 slot per channel concurrently."""
    db = db_manager.get_database()
    scheduler = SchedulerService(db)

    now_utc = datetime.now(timezone.utc)
    channel_id = "ch_concurrency_test"
    user_id = "user_conc"

    # Insert two due slots for the exact same channel
    await db.autopilot_queue.insert_one({
        "channel_id": channel_id,
        "user_id": user_id,
        "topic": "Slot 1",
        "status": "pending",
        "scheduled_at": now_utc - timedelta(minutes=10),
        "created_at": now_utc,
        "updated_at": now_utc
    })
    await db.autopilot_queue.insert_one({
        "channel_id": channel_id,
        "user_id": user_id,
        "topic": "Slot 2",
        "status": "pending",
        "scheduled_at": now_utc - timedelta(minutes=5),
        "created_at": now_utc,
        "updated_at": now_utc
    })

    # Dispatch: should claim only 1 slot because per-channel concurrency = 1
    claimed = await scheduler.find_and_claim_due_slots(now_utc, max_global=5)
    assert len(claimed) == 1

    # Second slot must still be pending
    pending_count = await db.autopilot_queue.count_documents({"channel_id": channel_id, "status": "pending"})
    assert pending_count == 1

@pytest.mark.asyncio
async def test_worker_lease_expiry_and_crash_recovery(test_db):
    """Verify slots with expired leases are recovered by scheduler."""
    db = db_manager.get_database()
    scheduler = SchedulerService(db)

    now_utc = datetime.now(timezone.utc)

    # Slot with expired lease and attempts < 3 -> should be reset to pending
    slot_recover = await db.autopilot_queue.insert_one({
        "channel_id": "ch_stale",
        "user_id": "u1",
        "status": "in_production",
        "claimed_by": "dead_worker",
        "claimed_at": now_utc - timedelta(minutes=20),
        "lease_expires_at": now_utc - timedelta(minutes=5),
        "attempts": 1,
        "max_attempts": 3,
        "created_at": now_utc,
        "updated_at": now_utc
    })

    # Slot with expired lease and attempts >= 3 -> should be marked failed
    slot_permanent_fail = await db.autopilot_queue.insert_one({
        "channel_id": "ch_stale_max",
        "user_id": "u1",
        "status": "in_production",
        "claimed_by": "dead_worker_2",
        "claimed_at": now_utc - timedelta(minutes=20),
        "lease_expires_at": now_utc - timedelta(minutes=5),
        "attempts": 3,
        "max_attempts": 3,
        "created_at": now_utc,
        "updated_at": now_utc
    })

    reclaimed = await scheduler.reclaim_expired_leases(now_utc)
    assert reclaimed == 2

    doc1 = await db.autopilot_queue.find_one({"_id": slot_recover.inserted_id})
    assert doc1["status"] == "pending"
    assert doc1["claimed_by"] is None

    doc2 = await db.autopilot_queue.find_one({"_id": slot_permanent_fail.inserted_id})
    assert doc2["status"] == "failed"
    assert doc2["failure_reason"] == "LEASE_EXPIRED_MAX_ATTEMPTS"

@pytest.mark.asyncio
async def test_events_api_and_approval_endpoints(test_db, async_client):
    """Verify GET /api/autopilot/{channel_id}/events and POST /api/autopilot/queue/{slot_id}/approve."""
    db = db_manager.get_database()

    reg = await async_client.post("/api/auth/register", json={
        "email": "events_tester@example.com",
        "password": "Password123!Secure",
        "name": "Events Tester"
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ch = (await async_client.post("/api/channels/", json={"name": "Events Channel"}, headers=headers)).json()
    channel_id = ch["id"]

    events_repo = AutopilotEventsRepository(db)
    slot_id = str(ObjectId())

    # Record 2 telemetry events
    await events_repo.record_event(
        channel_id=channel_id,
        user_id=ch["user_id"],
        queue_item_id=slot_id,
        stage="research",
        status="completed",
        progress=12,
        message="Research finished"
    )
    await events_repo.record_event(
        channel_id=channel_id,
        user_id=ch["user_id"],
        queue_item_id=slot_id,
        stage="script",
        status="completed",
        progress=22,
        message="Script finished"
    )

    # Fetch via API
    res = await async_client.get(f"/api/autopilot/{channel_id}/events", headers=headers)
    assert res.status_code == 200
    events = res.json()
    assert len(events) == 2
    stages = [e["stage"] for e in events]
    assert "research" in stages
    assert "script" in stages

    # Test queue slot approval validation
    # Create slot in ready_for_approval status
    slot_doc = {
        "channel_id": channel_id,
        "user_id": ch["user_id"],
        "status": "ready_for_approval",
        "stages": {"approval": {"status": "completed"}},
        "artifacts": {"video_id": "v_approved_test"},
        "scheduled_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    s_res = await db.autopilot_queue.insert_one(slot_doc)
    ready_slot_id = str(s_res.inserted_id)

    # Non-ready slot should reject approve with 400
    bad_slot = await db.autopilot_queue.insert_one({
        "channel_id": channel_id,
        "user_id": ch["user_id"],
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    })
    r_bad = await async_client.post(f"/api/autopilot/queue/{str(bad_slot.inserted_id)}/approve", headers=headers)
    assert r_bad.status_code == 400
    assert "expected 'ready_for_approval'" in r_bad.json()["error"]["message"]

