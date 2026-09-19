import pytest
import os
import hashlib
from datetime import datetime, timezone
from bson import ObjectId

from backend.app.database import db_manager
from backend.app.repositories.videos import VideoAssetRepository
from backend.app.video.composition.assembler import VideoAssembler, calculate_interval_union_coverage
from backend.app.video.composition.overlay import compute_safe_zone_position, resolve_platform_font
from backend.app.video.subtitles.generator import SubtitleGenerator, group_words_into_shorts_cues
from backend.app.autopilot.qa import QAEngine
from backend.app.autopilot.exceptions import QAGateError

@pytest.mark.asyncio
async def test_video_asset_repository_channel_isolation():
    db = db_manager.get_database()
    repo = VideoAssetRepository(db)

    user_a = str(ObjectId())
    chan_a = str(ObjectId())
    user_b = str(ObjectId())
    chan_b = str(ObjectId())

    # User A records an asset for Channel A
    asset_id_a = await repo.record_scene_provenance(
        user_id=user_a,
        channel_id=chan_a,
        video_id=str(ObjectId()),
        scene_id="scene_1",
        pexels_id=123456,
        photographer="Pexels Creator A",
        photographer_url="https://pexels.com/@creator_a",
        video_url="https://pexels.com/video/123456",
        download_url="https://video-files.pexels.com/123456/hd.mp4",
        width=1080,
        height=1920,
        duration=4.5,
        sha256="abc123sha256hash",
        local_path=f"media/videos/{chan_a}/clip_1.mp4",
        query="cyberpunk neon city",
        selected_at=datetime.now(timezone.utc).isoformat()
    )
    assert asset_id_a is not None

    # Query for Channel A
    chan_a_assets = await repo.find_by_channel(channel_id=chan_a, user_id=user_a)
    assert len(chan_a_assets) >= 1
    found_a = [a for a in chan_a_assets if str(a["_id"]) == asset_id_a]
    assert len(found_a) == 1
    assert found_a[0]["pexels_id"] == 123456
    assert found_a[0]["photographer"] == "Pexels Creator A"
    assert found_a[0]["sha256"] == "abc123sha256hash"

    # Strict Channel Isolation: Querying with Channel B or User B MUST NOT return Channel A's asset
    chan_b_assets = await repo.find_by_channel(channel_id=chan_b, user_id=user_b)
    b_ids = [str(a["_id"]) for a in chan_b_assets]
    assert asset_id_a not in b_ids

    # Querying with user_b on channel_a MUST return empty
    spoofed_assets = await repo.find_by_channel(channel_id=chan_a, user_id=user_b)
    assert len(spoofed_assets) == 0

    # Cleanup test doc
    await repo.delete_one(asset_id_a)


@pytest.mark.asyncio
async def test_provenance_full_field_roundtrip():
    db = db_manager.get_database()
    repo = VideoAssetRepository(db)

    user_id = str(ObjectId())
    chan_id = str(ObjectId())
    vid_id = str(ObjectId())

    test_sha = hashlib.sha256(b"auvyra_test_provenance_asset").hexdigest()
    asset_id = await repo.record_scene_provenance(
        user_id=user_id,
        channel_id=chan_id,
        video_id=vid_id,
        scene_id="scene_2",
        pexels_id=987654,
        photographer="Jane Filmmaker",
        photographer_url="https://pexels.com/@jane",
        video_url="https://pexels.com/video/987654",
        download_url="https://video-files.pexels.com/987654/fullhd.mp4",
        width=1080,
        height=1920,
        duration=5.2,
        sha256=test_sha,
        local_path=f"media/videos/{chan_id}/scene_2.mp4",
        query="futuristic artificial intelligence robot",
        selected_at=datetime.now(timezone.utc).isoformat()
    )

    doc = await repo.find_by_id(asset_id)
    assert doc is not None
    assert doc["user_id"] == user_id
    assert doc["channel_id"] == chan_id
    assert doc["video_id"] == vid_id
    assert doc["scene_id"] == "scene_2"
    assert doc["pexels_id"] == 987654
    assert doc["photographer"] == "Jane Filmmaker"
    assert doc["sha256"] == test_sha
    assert doc["query"] == "futuristic artificial intelligence robot"

    # Cleanup
    await repo.delete_one(asset_id)


def test_caption_safe_zone_geometry_and_density():
    # 1. Test cadence grouping
    words = [
        {"word": "Autonomous", "start": 0.0, "end": 0.5},
        {"word": "agents", "start": 0.5, "end": 0.9},
        {"word": "generate", "start": 0.9, "end": 1.3},
        {"word": "revenue", "start": 1.3, "end": 1.7},
        {"word": "effortlessly.", "start": 1.7, "end": 2.2},
    ]
    cues = group_words_into_shorts_cues(words)
    assert len(cues) >= 2
    avg_words = sum(c["word_count"] for c in cues) / len(cues)
    assert avg_words <= 3.5

    # 2. Test geometry calculations for 1080x1920 canvas
    H = 1920
    for box_h in [50, 100, 150, 200]:
        y_pos, top_r, bot_r = compute_safe_zone_position(box_h, H, 0.62, 0.76, 0.70)
        assert top_r >= 0.619
        assert bot_r <= 0.761
        # Absolute pixel positions within [1190, 1460]
        assert y_pos >= 1190
        assert (y_pos + box_h) <= 1460


def test_interval_union_stock_coverage_boundary():
    # Target duration 30s.
    # 3 clips covering 0-10, 10-20, 20-30 -> 100% coverage
    full_intervals = [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]
    u_dur, ratio = calculate_interval_union_coverage(full_intervals, 30.0)
    assert u_dur == 30.0
    assert ratio == 1.0

    # Deficient coverage: 0-5, 10-15 -> 10s out of 30s -> 33.3% (< 70%)
    deficient_intervals = [(0.0, 5.0), (10.0, 15.0)]
    u_dur_def, ratio_def = calculate_interval_union_coverage(deficient_intervals, 30.0)
    assert u_dur_def == 10.0
    assert ratio_def < 0.70

