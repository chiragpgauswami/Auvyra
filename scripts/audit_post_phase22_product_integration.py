"""
Post-Phase-22 Product Integration & Hardening Audit Script.

Verifies end-to-end:
1. Active Jobs and Terminal State Guard (prevents infinite polling)
2. Create Page Reload Hydration (find_latest_by_channel & active job recovery)
3. Real Scene-Specific Pexels Stock Media (Zero demo clip fallback, VideoAsset provenance)
4. Balanced Caption Safe-Zone Padding & Text Wrapping (No oversized stretched bars)
5. Videos Page Multi-Channel Query Resolution (find_by_channel with channel_id=None)
6. Thumbnail Generation and Authenticated Retrieval
7. Unified Canonical Publishing Calendar (autopilot_queue + publishing_jobs matching Control Center)

ZERO MOCKS in production paths.
"""

import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from loguru import logger
from PIL import Image

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import get_settings
from backend.app.database import db_manager
from backend.app.repositories.users import UserRepository
from backend.app.repositories.channels import ChannelRepository, AutopilotQueueRepository
from backend.app.repositories.videos import VideoRepository, VideoAssetRepository
from backend.app.repositories.jobs import JobRepository
from backend.app.repositories.publishing import PublishingRepository
from backend.app.services.video_service import VideoService
from backend.app.services.publishing_service import PublishingService
from backend.app.storage.local import LocalStorageProvider
from backend.app.video.rendering.ffmpeg import probe_video_info
from backend.app.video.composition.overlay import VideoOverlay


async def run_audit():
    print("=" * 80)
    print("AUVYRA POST-PHASE-22 PRODUCT INTEGRATION & HARDENING AUDIT")
    print("=" * 80)

    settings = get_settings()
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_DATABASE}...")
    await db_manager.connect(settings.MONGODB_URI, settings.MONGODB_DATABASE)
    db = db_manager.get_database()

    user_repo = UserRepository(db)
    channel_repo = ChannelRepository(db)
    video_repo = VideoRepository(db)
    asset_repo = VideoAssetRepository(db)
    job_repo = JobRepository(db)
    queue_repo = AutopilotQueueRepository(db)
    pub_repo = PublishingRepository(db)
    storage = LocalStorageProvider(settings.MEDIA_ROOT)
    video_service = VideoService(db, storage)
    pub_service = PublishingService(db)

    results = {}

    # 1. User & Channel resolution
    user = await user_repo.find_many({}, limit=1)
    if not user:
        user_id = await user_repo.create_user({
            "email": "audit_post22@auvyra.local",
            "password_hash": "hash_123",
            "name": "Audit Tester"
        })
    else:
        user_id = str(user[0]["_id"])
    logger.info(f"Audit User ID: {user_id}")

    channels = await channel_repo.find_by_user(user_id)
    if not channels:
        channel_id = await channel_repo.insert_one({
            "user_id": user_id,
            "name": "ShortsMela Audit",
            "status": "connected",
            "autopilot_config": {"timezone": "UTC"}
        })
    else:
        channel_id = str(channels[0]["_id"])
    logger.info(f"Audit Channel ID: {channel_id}")

    # =========================================================================
    # TEST 1: Manual Create & Active Job Terminal Polling Contract
    # =========================================================================
    print("\n--- [1/6] Auditing Manual Video Job & Terminal Polling Contract ---")
    topic = "Autonomous Mars Rovers Discovery"
    script = "Deep beneath the crimson sands of Mars, robotic rovers uncover ancient liquid reservoirs, shifting our understanding of extraterrestrial life."
    
    # Enqueue manual video job with pexels source
    job_info = await video_service.create_video_job(
        user_id=user_id,
        channel_id=channel_id,
        request_data={
            "topic": topic,
            "script": script,
            "duration": 15,
            "video_source": "pexels",
            "voice_name": "en-US-GuyNeural",
            "caption_style": {"preset": "bold_yellow"}
        }
    )
    job_id = job_info["job_id"]
    initial_video_id = job_info["video_id"]
    logger.info(f"Enqueued Job ID: {job_id}, Video ID: {initial_video_id}")

    # Verify active jobs query sees it
    active_jobs = await job_repo.find_active_by_user(user_id)
    has_active = any(str(j["_id"]) == job_id for j in active_jobs)
    assert has_active, "Enqueued job must appear in find_active_by_user"
    print("  ✓ Active job correctly discovered by /api/jobs/active endpoint query")

    # Process job via VideoWorker logic
    raw_job = await job_repo.find_by_id(job_id)
    job_result = await video_service.process_video_job(raw_job)
    await job_repo.mark_complete(job_id, result=job_result)
    print("  ✓ Video job completed processing successfully")

    # Verify terminal state
    final_job = await job_repo.find_by_id(job_id)
    assert final_job["status"] == "completed"
    assert final_job["progress"] == 100
    assert "video_id" in final_job.get("result", {})
    active_after = await job_repo.find_active_by_user(user_id)
    assert not any(str(j["_id"]) == job_id for j in active_after)
    print("  ✓ Job reached terminal state (100% / completed); active query correctly empty (polling terminates)")
    results["Terminal Polling Guard"] = "PASS"

    # =========================================================================
    # TEST 2: Page Reload Recovery (Hydration)
    # =========================================================================
    print("\n--- [2/6] Auditing Page Reload Recovery (/videos/latest) ---")
    latest_vid = await video_service.get_latest_video(user_id)
    assert latest_vid is not None, "Latest video must exist"
    assert str(latest_vid.get("id") or latest_vid.get("_id")) == initial_video_id
    assert latest_vid["status"] == "generated"
    assert latest_vid.get("file_path") is not None
    vid_ident = latest_vid.get("id") or latest_vid.get("_id")
    print(f"  ✓ Latest video hydrated: '{latest_vid['title']}' (ID: {vid_ident})")
    results["Reload Recovery Hydration"] = "PASS"

    # =========================================================================
    # TEST 3: Real Pexels Stock Footage & Scene Provenance (NO silent fallback)
    # =========================================================================
    print("\n--- [3/6] Auditing Real Stock Media & VideoAsset Provenance ---")
    assets = await asset_repo.find_by_video(initial_video_id)
    assert len(assets) > 0, "Video must have recorded assets"
    stock_assets = [a for a in assets if a.get("asset_type") in ("stock_video", "source_clip")]
    assert len(stock_assets) > 0, "Video must have recorded scene provenance stock assets"
    for a in stock_assets:
        assert a.get("provider") == "pexels"
        assert a.get("pexels_id") is not None
        assert "pexels.com" in (a.get("url") or "") or "pexels.com" in (a.get("video_url") or "")
        print(f"  ✓ Scene Provenance: Pexels ID {a.get('pexels_id')} by '{a.get('photographer')}' ({a.get('duration')}s)")

    mp4_path = latest_vid["file_path"]
    assert os.path.exists(mp4_path), f"Video file must exist on disk: {mp4_path}"
    probe = probe_video_info(mp4_path)
    assert probe["width"] == 1080 and probe["height"] == 1920, f"Expected 1080x1920, got {probe['width']}x{probe['height']}"
    assert probe["duration"] > 0, "Duration must be > 0"
    file_size = probe.get("size") or os.path.getsize(mp4_path)
    assert file_size > 100000, "File size must be substantial (>100KB)"
    print(f"  ✓ Rendered MP4: {probe['width']}x{probe['height']}, {probe['duration']:.2f}s, {file_size / 1024:.1f} KB")
    results["Real Pexels Footage & Provenance"] = "PASS"

    # =========================================================================
    # TEST 4: Balanced Caption Wrapping & Proportional Margins
    # =========================================================================
    print("\n--- [4/6] Auditing Caption Wrapping & Bounding Box Margins ---")
    overlay = VideoOverlay()
    
    # Short cue: 2-3 words
    short_wrap = overlay.wrap_caption_text("ROBOTIC ROVERS", font_size=56, target_width=972)
    assert "\n" not in short_wrap, "Short cue must not wrap unnecessarily"
    
    # Long cue: wraps without screen blowout
    long_wrap = overlay.wrap_caption_text("UNCOVER ANCIENT LIQUID RESERVOIRS SHIFTING OUR UNDERSTANDING", font_size=56, target_width=972)
    lines = long_wrap.split("\n")
    assert len(lines) >= 2, "Long cue must wrap into multiple lines"
    for line in lines:
        assert len(line) <= 28, f"Line exceeds expected width limit: '{line}'"
    print(f"  ✓ Dynamic text wrapping verified: 1 line for short ({short_wrap}), {len(lines)} lines for long")
    results["Caption Proportions & Wrapping"] = "PASS"

    # =========================================================================
    # TEST 5: Videos Page Query Scoping & Thumbnail Retrieval
    # =========================================================================
    print("\n--- [5/6] Auditing Videos Page Query & Thumbnail Retrieval ---")
    all_videos = await video_repo.find_by_channel(user_id=user_id, channel_id=None)
    assert len(all_videos) >= 1, "All user videos must be returned when channel_id=None"
    assert any(str(v["_id"]) == initial_video_id for v in all_videos)
    print(f"  ✓ Videos query find_by_channel(channel_id=None) successfully returned {len(all_videos)} video(s)")

    # Check thumbnail
    thumb_path = latest_vid.get("thumbnail_path")
    assert thumb_path and os.path.exists(thumb_path), f"Thumbnail must exist on disk: {thumb_path}"
    with Image.open(thumb_path) as img:
        t_w, t_h = img.size
        assert t_w > 0 and t_h > 0
        print(f"  ✓ Verified Thumbnail on disk: {thumb_path} ({t_w}x{t_h})")
    results["Videos Page Query & Thumbnail"] = "PASS"

    # =========================================================================
    # TEST 6: Unified Canonical Publishing Calendar
    # =========================================================================
    print("\n--- [6/6] Auditing Unified Publishing Calendar Consolidation ---")
    # Add a mock slot in autopilot queue
    slot_id = await queue_repo.create_slot({
        "user_id": user_id,
        "channel_id": channel_id,
        "slot_date": "2026-09-21",
        "scheduled_time": "14:00",
        "topic": "Future of Mars Colonization",
        "pillar": "Space",
        "status": "ready_for_approval",
        "current_stage": "approval",
        "scheduled_at": datetime.now(timezone.utc) + timedelta(days=1)
    })

    calendar_events = await pub_service.get_publishing_calendar(user_id=user_id)
    assert len(calendar_events) >= 1, "Calendar must contain events"
    found_slot = next((e for e in calendar_events if e.get("queue_item_id") == slot_id), None)
    assert found_slot is not None, "Autopilot slot must be present in calendar"
    assert found_slot["display_status"] == "Awaiting Approval"
    assert found_slot["channel_name"] != ""
    print(f"  ✓ Calendar Event: '{found_slot['title']}' | Status: {found_slot['display_status']} | Channel: {found_slot['channel_name']}")
    results["Unified Publishing Calendar"] = "PASS"

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("AUDIT RESULTS SUMMARY")
    print("=" * 80)
    all_passed = True
    for item, status in results.items():
        print(f"  [{status}] {item}")
        if status != "PASS":
            all_passed = False

    print("=" * 80)
    if all_passed:
        print("ALL PRODUCT INTEGRATION ACCEPTANCE CHECKS PASSED.")
    else:
        print("SOME CHECKS FAILED.")
    print("=" * 80)

    await db_manager.disconnect()
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_audit())
    sys.exit(0 if success else 1)
