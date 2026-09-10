import os
import glob
import pytest
from PIL import Image
from backend.app.models.metadata import VideoMetadataPackage
from backend.app.services.metadata_service import MetadataService
from backend.app.services.thumbnail_service import ThumbnailService

def test_video_metadata_model():
    data = {
        "title": "Insane AI Productivity Secret That Changed Coding Forever In 2026\n",
        "description": "Full description of the video with all key insights and details.",
        "tags": ["ai", "coding", "software engineering", "productivity", "python"],
        "hashtags": ["ai", "#tech", "coding"],
        "thumbnail_text_overlay": "STOP CODING LIKE THIS"
    }

    pkg = VideoMetadataPackage(**data)
    assert "\n" not in pkg.title
    assert len(pkg.title) <= 100
    assert len(pkg.tags) == 5
    assert all(h.startswith("#") for h in pkg.hashtags)
    assert pkg.thumbnail_text_overlay == "STOP CODING LIKE THIS"

@pytest.mark.asyncio
async def test_metadata_service_heuristic():
    service = MetadataService(ai_gateway=None)
    pkg = await service.generate_metadata(
        topic="Modern AI Workflow Automation",
        script="Today we explore three ways to automate your daily tasks using open-source models.",
        channel_context={"niche": "Technology", "winning_hooks": []}
    )

    assert isinstance(pkg, VideoMetadataPackage)
    assert len(pkg.title) > 5
    assert len(pkg.title_candidates) >= 3
    assert len(pkg.tags) >= 5
    assert "#Technology" in pkg.hashtags or "#technology" in pkg.hashtags
    assert len(pkg.thumbnail_text_overlay) > 0

def test_thumbnail_generation_from_video(tmp_path):
    stock_clips = glob.glob("media/test_pexels_run/*.mp4") + glob.glob("media/cache/pexels/*.mp4")
    video_source = stock_clips[0] if stock_clips else None

    service = ThumbnailService(output_dir=str(tmp_path))
    thumb_path = service.generate_thumbnail(
        video_path=video_source,
        text_overlay="DO NOT MISS THIS",
        output_filename="test_thumb.jpg",
        target_width=1080,
        target_height=1920
    )

    assert os.path.exists(thumb_path)
    file_size = os.path.getsize(thumb_path)
    assert file_size > 10000
    assert file_size <= 2 * 1024 * 1024  # YouTube limit: 2MB

    # Verify image dimensions
    with Image.open(thumb_path) as img:
        assert img.size == (1080, 1920)
        assert img.format == "JPEG"
