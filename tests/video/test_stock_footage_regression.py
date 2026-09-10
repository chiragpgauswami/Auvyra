import os
import glob
import pytest
from backend.app.video.models import MediaItem, VideoAspect
from backend.app.video.storyboard import VisualScene
from backend.app.video.composition.assembler import VideoAssembler
from backend.app.video.validation import validate_video_content
from backend.app.video.rendering.ffmpeg import probe_video_info

def test_stock_footage_assembly_regression(tmp_path):
    # Locate cached real stock video clips from Pexels run
    stock_clips = glob.glob("media/test_pexels_run/*.mp4") + glob.glob("media/cache/pexels/*.mp4")
    if not stock_clips:
        pytest.skip("No local stock video clips available for composition regression test")

    clip1 = stock_clips[0]
    clip2 = stock_clips[1] if len(stock_clips) > 1 else stock_clips[0]

    media_items = [
        MediaItem(
            provider="pexels",
            url="https://example.com/video1.mp4",
            local_path=os.path.abspath(clip1),
            duration=5.0,
            scene_index=1
        ),
        MediaItem(
            provider="pexels",
            url="https://example.com/video2.mp4",
            local_path=os.path.abspath(clip2),
            duration=5.0,
            scene_index=2
        )
    ]

    scenes = [
        VisualScene(scene_index=1, text="Scene 1 narration", duration=3.0, search_queries=["developer"]),
        VisualScene(scene_index=2, text="Scene 2 narration", duration=3.0, search_queries=["robot"])
    ]

    assembler = VideoAssembler()
    output_video = str(tmp_path / "test_composed_output.mp4")

    result_path = assembler.assemble_storyboard_scenes(
        storyboard_scenes=scenes,
        media_items=media_items,
        audio_duration=6.0,
        aspect_ratio=VideoAspect.portrait,
        output_path=output_video,
        fit_mode="cover"
    )

    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 50000

    info = probe_video_info(result_path)
    assert info["width"] == 1080
    assert info["height"] == 1920
    assert info["duration"] >= 5.5

    # Run frame visual analysis
    qa_report = validate_video_content(result_path, expected_duration=6.0, qa_dir=str(tmp_path / "qa"))
    assert len(qa_report.frame_metrics) > 0

    # Ensure no blank void frames and sufficient visual texture
    for frame in qa_report.frame_metrics:
        assert not frame.is_blank, f"Frame at {frame.timestamp}s is blank/static void!"
        assert frame.pixel_variance >= 10.0, f"Frame variance {frame.pixel_variance} is too low (synthetic gradient)!"
