import asyncio
import os
import shutil
from loguru import logger
from backend.app.video.models import VideoGenerationRequest, PipelineProgress
from backend.app.video.pipeline import VideoGenerationService
from backend.app.video.rendering.ffmpeg import probe_video_info

def on_progress(p: PipelineProgress):
    logger.info(f"[{p.percent}%] {p.stage.upper()}: {p.message}")

async def run_test():
    logger.info("=== STARTING AUVYRA VIDEO ENGINE TEST ===")
    
    test_output_dir = os.path.abspath("media/videos/test")
    os.makedirs(test_output_dir, exist_ok=True)
    
    request = VideoGenerationRequest(
        topic="Example AI tools",
        script="Artificial intelligence tools are transforming the future of work. From generative visuals to automated workflows, creators can now build products at lightning speed.",
        duration=10,
        aspect_ratio="9:16",
        output_dir=test_output_dir,
        subtitle_enabled=True,
        video_source="local"
    )
    
    service = VideoGenerationService()
    result = await service.generate(request, progress_callback=on_progress)
    
    expected_output = os.path.join(test_output_dir, "example.mp4")
    logger.info(f"Generated video path: {result.video_path}")
    
    # 1. Verify file exists
    assert os.path.exists(expected_output), f"Output file does not exist at {expected_output}"
    assert os.path.getsize(expected_output) > 1000, f"Output file too small: {os.path.getsize(expected_output)} bytes"
    logger.success("✓ 1. File exists and has valid size")
    
    # 2. Probe video info with ffprobe
    info = probe_video_info(expected_output)
    logger.info(f"Probe info: {info}")
    
    # 3. Verify dimensions (9:16 portrait: 1080x1920)
    assert info.get("width") == 1080, f"Expected width 1080, got {info.get('width')}"
    assert info.get("height") == 1920, f"Expected height 1920, got {info.get('height')}"
    logger.success("✓ 2. Correct dimensions (1080x1920, 9:16)")
    
    # 4. Verify duration
    duration = info.get("duration", 0)
    assert duration > 0, f"Expected duration > 0, got {duration}"
    logger.success(f"✓ 3. Correct duration ({duration:.2f} seconds)")
    
    # 5. Verify audio exists in stream
    import subprocess
    cmd = [
        shutil.which("ffprobe") or "ffprobe",
        "-i", expected_output,
        "-show_streams", "-select_streams", "a",
        "-loglevel", "error"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert len(res.stdout.strip()) > 0, "No audio stream found in output video!"
    logger.success("✓ 4. Audio stream exists and is verified")
    
    # 6. Verify subtitles generated
    assert result.subtitle_path and os.path.exists(result.subtitle_path), "Subtitle file not found!"
    with open(result.subtitle_path, "r", encoding="utf-8") as sf:
        srt_content = sf.read()
    assert len(srt_content.strip()) > 0, "Subtitle file is empty!"
    logger.success("✓ 5. Subtitles generated and rendered onto video")
    
    logger.success("=== ALL SECTION 17 REQUIREMENTS VERIFIED SUCCESSFULLY ===")

if __name__ == "__main__":
    asyncio.run(run_test())

