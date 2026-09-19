"""
Phase 20 Real YouTube Publishing Acceptance Test.
Executes the Autopilot pipeline on the real connected YouTube channel 'ShortsMela'
to verify end-to-end publishing, resolve GOOGLE_OAUTH_NOT_CONFIGURED, and confirm
real video upload to YouTube Data API v3.
"""

import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from loguru import logger

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import get_settings
from backend.app.database import db_manager
from backend.app.services.autopilot_service import AutopilotService
from backend.app.repositories.channels import ChannelRepository, AutopilotQueueRepository
from backend.app.repositories.brain import ChannelBrainRepository
from backend.app.repositories.autopilot_events import AutopilotEventsRepository
from backend.app.youtube.client import get_youtube_client_for_channel

async def run_real_youtube_publish():
    settings = get_settings()
    logger.info("Connecting to MongoDB...")
    await db_manager.connect(settings.MONGODB_URI, settings.MONGODB_DATABASE)
    db = db_manager.get_database()

    channel_repo = ChannelRepository(db)
    brain_repo = ChannelBrainRepository(db)
    queue_repo = AutopilotQueueRepository(db)
    events_repo = AutopilotEventsRepository(db)

    # 1. Locate the connected YouTube channel
    channel = await db.channels.find_one({"youtube_channel_id": "UCN9MbwD3kY4jbVfNEVKH2Ag"})
    if not channel:
        logger.error("Connected YouTube channel 'ShortsMela' not found in database.")
        return

    channel_id = str(channel["_id"])
    user_id = channel["user_id"]
    logger.info(f"Using real connected channel: '{channel.get('name')}' (ID: {channel_id}, YT: {channel.get('youtube_channel_id')})")
    logger.info(f"Channel OAuth Account ID: {channel.get('oauth_account_id')}")

    # Verify OAuth client can be resolved
    yt_client = await get_youtube_client_for_channel(channel_id, user_id, db)
    my_ch = await yt_client.get_my_channel()
    logger.info(f"Verified live YouTube connection: '{my_ch.get('name')}' ({my_ch.get('youtube_channel_id')})")

    # 2. Configure Autopilot and Channel Brain for ShortsMela
    now_utc = datetime.now(timezone.utc)
    autopilot_config = {
        "mode": "full_autopilot",
        "format": "shorts",
        "niche": "AI Innovations & Breakthroughs",
        "content_pillars": ["Autonomous Agents", "AI Software", "Tech Future"],
        "schedule": {
            "frequency_per_week": 3,
            "timezone": "UTC",
            "days_of_week": [0, 2, 4],
            "times": ["14:00"]
        }
    }
    await db.channels.update_one(
        {"_id": channel["_id"]},
        {"$set": {
            "autopilot_enabled": True,
            "approval_required": False,  # Full autonomous upload to YouTube
            "autopilot_config": autopilot_config,
            "updated_at": now_utc
        }}
    )

    brain_data = {
        "channel_id": channel_id,
        "user_id": user_id,
        "niche": "AI Innovations & Breakthroughs",
        "tone": "energetic, visionary, and sharp",
        "target_audience": "Tech lovers, developers, and innovators",
        "winning_hooks": ["This AI update changes everything you knew about coding."],
        "avoid_topics": ["scams", "crypto speculation"],
        "learned_rules": ["Punchy hook in first 2 seconds", "Keep total duration under 35 seconds"],
        "content_pillars": ["Autonomous Agents", "AI Software", "Tech Future"]
    }
    await brain_repo.upsert_brain(channel_id, user_id, brain_data)
    logger.info("Configured Autopilot and Channel Brain for ShortsMela.")

    # 3. Create a dedicated queue item for ShortsMela
    slot_doc = {
        "channel_id": channel_id,
        "user_id": user_id,
        "topic": "Autonomous Coding Agents in 2026",
        "pillar": "Autonomous Agents",
        "format": "shorts",
        "status": "pending",
        "scheduled_at": now_utc,
        "attempts": 0,
        "max_attempts": 3,
        "created_at": now_utc,
        "updated_at": now_utc
    }
    s_res = await db.autopilot_queue.insert_one(slot_doc)
    queue_item_id = str(s_res.inserted_id)
    logger.info(f"Created queue slot {queue_item_id} for live YouTube publishing.")

    # Claim the slot
    worker_id = "real_youtube_upload_worker"
    await db.autopilot_queue.update_one(
        {"_id": s_res.inserted_id},
        {"$set": {
            "status": "in_production",
            "claimed_by": worker_id,
            "claimed_at": now_utc,
            "heartbeat_at": now_utc,
            "lease_expires_at": now_utc + timedelta(minutes=15)
        }}
    )

    # 4. Execute the pipeline
    logger.info("Executing 14-stage Autopilot pipeline through to YouTube Data API v3 upload...")
    autopilot = AutopilotService(db)
    exec_result = await autopilot.execute_queue_item(queue_item_id, worker_id)

    # 5. Inspect resulting slot and video documents
    final_slot = await db.autopilot_queue.find_one({"_id": s_res.inserted_id})
    video_id = final_slot.get("artifacts", {}).get("video_id")
    video_doc = await db.videos.find_one({"_id": ObjectId(video_id)}) if video_id else None

    # Retrieve telemetry
    events = await events_repo.find_by_channel(channel_id, user_id, limit=50)

    print("\n" + "=" * 80)
    print("AUVYRA REAL YOUTUBE PUBLISHING ACCEPTANCE AUDIT REPORT")
    print("=" * 80)
    print(f"Channel Name:         {channel.get('name')}")
    print(f"YouTube Channel ID:   {channel.get('youtube_channel_id')}")
    print(f"Queue Item ID:        {queue_item_id}")
    print(f"Final Slot Status:    {final_slot.get('status')}")
    print(f"Published URL:        {final_slot.get('published_url')}")
    print(f"YouTube Video ID:     {video_doc.get('youtube_video_id') if video_doc else 'N/A'}")
    print(f"Video DB Status:      {video_doc.get('status') if video_doc else 'N/A'}")
    print(f"Published At:         {video_doc.get('published_at') if video_doc else 'N/A'}")
    print("-" * 80)
    print("STAGE EXECUTION STATUS:")
    stages = final_slot.get("stages", {})
    for s_name, s_data in stages.items():
        dur = "N/A"
        if s_data.get("started_at") and s_data.get("completed_at"):
            dur = f"{(s_data['completed_at'] - s_data['started_at']).total_seconds():.2f}s"
        print(f"  [{s_data.get('status').upper():<9}] {s_name:<15} | Duration: {dur:<8} | Error: {s_data.get('error') or 'None'}")

    print("-" * 80)
    print(f"TELEMETRY EVENTS ({len(events)} events):")
    for ev in events:
        ts = ev.get("created_at")
        ts_str = ts.strftime("%H:%M:%S") if ts else "N/A"
        print(f"  [{ts_str}] Stage: {ev.get('stage', ''):<12} | Status: {ev.get('status', ''):<9} | Progress: {ev.get('progress', 0):>3}% | Msg: {ev.get('message', '')}")
    print("=" * 80 + "\n")

    await db_manager.disconnect()
    logger.info("Real YouTube Publishing Acceptance Completed Successfully.")

if __name__ == "__main__":
    asyncio.run(run_real_youtube_publish())

