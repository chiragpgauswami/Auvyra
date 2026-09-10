import asyncio
import os
import sys
import time
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from backend.app.video.media.pexels_stock_service import PexelsStockService
from backend.app.video.models import VideoAspect
from backend.app.video.storyboard import VisualScene, VisualStoryboard

async def main():
    print("=" * 60)
    print("AUVYRA PEXELS STOCK VIDEO PIPELINE DIAGNOSTIC")
    print("=" * 60)

    api_key = os.getenv("PEXELS_API_KEY", "")
    if not api_key:
        print("❌ ERROR: PEXELS_API_KEY is not set in environment!")
        sys.exit(1)

    print(f"🔑 Pexels API Key configured: {api_key[:6]}...{api_key[-4:]}")

    test_dir = os.path.abspath("media/test_pexels_run")
    os.makedirs(test_dir, exist_ok=True)
    cache_dir = os.path.abspath("media/cache/pexels")

    service = PexelsStockService(api_keys=api_key, cache_dir=cache_dir)

    # 1. Test Search and Quality Candidate Ranking
    print("\n[1/4] Searching candidates for 'developer typing laptop neon'...")
    candidates = await service.search_candidates("developer typing laptop neon", aspect_ratio=VideoAspect.portrait, min_duration=2.0)
    print(f"   Found {len(candidates)} candidates.")
    assert len(candidates) > 0, "Expected at least 1 candidate video from Pexels"
    first = candidates[0]
    print(f"   Top candidate: {first.width}x{first.height}, duration={first.duration:.1f}s, url={first.url[:50]}...")
    assert first.height >= 720 or first.width >= 720, "Video resolution below 720p threshold"
    print("   ✅ Candidate quality ranking PASSED.")

    # 2. Test Download & Disk Caching
    print("\n[2/4] Testing streaming download...")
    t0 = time.time()
    dest_path1 = await service.download_video(first, test_dir)
    dt1 = time.time() - t0
    print(f"   Downloaded to: {dest_path1} in {dt1:.2f}s ({os.path.getsize(dest_path1)} bytes)")
    assert os.path.exists(dest_path1) and os.path.getsize(dest_path1) > 50000, "Downloaded video file missing or empty"

    print("\n[3/4] Testing SHA-256 disk cache reuse...")
    t1 = time.time()
    dest_path2 = await service.download_video(first, test_dir)
    dt2 = time.time() - t1
    print(f"   Cached retrieval in {dt2:.4f}s")
    assert dt2 < 0.2, f"Cache retrieval was slow: {dt2}s"
    print("   ✅ SHA-256 Disk Cache PASSED.")

    # 3. Test Full Multi-Scene Storyboard Media Resolution
    print("\n[4/4] Testing multi-scene storyboard media resolution...")
    storyboard = VisualStoryboard(
        title="AI Developer Workflow",
        total_duration=9.0,
        aspect_ratio="9:16",
        scenes=[
            VisualScene(scene_index=1, text="Coding used to take days.", duration=3.0, search_queries=["stressed software developer desk", "monochrome code terminal"]),
            VisualScene(scene_index=2, text="Now autonomous agents build the scaffold.", duration=3.0, search_queries=["server room neon matrix data", "futuristic robot technology"]),
            VisualScene(scene_index=3, text="Subscribe for more leverage.", duration=3.0, search_queries=["smartphone vertical screen app", "smiling entrepreneur laptop"])
        ]
    )

    media_items = await service.fetch_media_for_storyboard(storyboard, test_dir, aspect_ratio=VideoAspect.portrait)
    print(f"   Resolved {len(media_items)} clips for {len(storyboard.scenes)} scenes.")
    for item in media_items:
        print(f"   Scene {item.scene_index}: {item.width}x{item.height}, {item.duration:.1f}s -> {os.path.basename(item.local_path)}")
        assert os.path.exists(item.local_path)
        assert os.path.getsize(item.local_path) > 50000

    coverage = len(media_items) / len(storyboard.scenes) * 100
    print(f"   Stock video timeline coverage: {coverage:.1f}%")
    assert coverage >= 66.6, f"Stock video coverage too low: {coverage}%"
    print("   ✅ Multi-scene stock resolution PASSED.")

    print("\n" + "=" * 60)
    print("🎉 ALL PEXELS STOCK VIDEO PIPELINE DIAGNOSTICS PASSED (100% LIVE)")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
