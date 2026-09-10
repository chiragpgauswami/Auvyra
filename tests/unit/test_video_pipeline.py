import os
import pytest
from backend.app.video.models import VideoGenerationRequest, VideoAspect
from backend.app.video.subtitles.srt_parser import format_timestamp, parse_srt, text_to_srt
from backend.app.video.rendering.ffmpeg import get_effective_codec, probe_video_info
from backend.app.video.audio.edge_tts_provider import EdgeTTSProvider

def test_video_aspect_resolution():
    assert VideoAspect.landscape.to_resolution() == (1920, 1080)
    assert VideoAspect.portrait.to_resolution() == (1080, 1920)
    assert VideoAspect.square.to_resolution() == (1080, 1080)

def test_video_generation_request_defaults():
    req = VideoGenerationRequest(topic="Artificial Intelligence")
    assert req.aspect_ratio == "9:16"
    assert req.subtitle_enabled is True
    assert req.voice_name == "en-US-AriaNeural-Female"

def test_srt_parser_and_formatter():
    ts = format_timestamp(65.123)
    assert ts == "00:01:05,123"

    entry = text_to_srt(1, "Hello world", 0.0, 2.5)
    assert "1" in entry
    assert "00:00:00,000 --> 00:00:02,500" in entry
    assert "Hello world" in entry

def test_edge_tts_voice_cleaning():
    provider = EdgeTTSProvider()
    clean_voice = provider._clean_voice_name("en-US-AriaNeural-Female")
    assert clean_voice == "en-US-AriaNeural"
    assert provider._format_voice_rate(1.2) == "+20%"
    assert provider._format_voice_rate(0.8) == "-20%"

def test_ffmpeg_codec_resolution():
    codec = get_effective_codec("libx264")
    assert codec in ["libx264", "h264_videotoolbox", "h264_nvenc"]

def test_validate_media_asset_nonexistent():
    from backend.app.video.validation import validate_media_asset
    is_valid, msg = validate_media_asset("/nonexistent/video.mp4")
    assert is_valid is False
    assert "does not exist" in msg

def test_validate_video_content_nonexistent():
    from backend.app.video.validation import validate_video_content
    report = validate_video_content("/nonexistent/video.mp4")
    assert report.is_valid is False
    assert len(report.failure_reasons) > 0


