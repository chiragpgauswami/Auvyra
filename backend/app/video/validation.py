import os
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image
from loguru import logger

@dataclass
class FrameMetrics:
    percentage: float
    timestamp: float
    frame_path: str
    mean_luminance: float
    pixel_variance: float
    near_black_ratio: float  # Percentage of pixels with luminance < 12
    is_blank: bool

@dataclass
class VisualQAReport:
    is_valid: bool
    video_path: str
    duration: float
    width: int
    height: int
    fps: float
    total_frames: int
    audio_valid: bool
    audio_codec: str
    audio_duration: float
    audio_mean_volume_db: float
    sync_valid: bool
    frame_metrics: List[FrameMetrics] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
    qa_artifact_dir: str = ""

def validate_media_asset(file_path: str, min_duration: float = 0.5) -> Tuple[bool, str]:
    """Verify that a source media asset exists, is readable, and contains valid decodable video."""
    if not os.path.exists(file_path):
        return False, f"File does not exist: {file_path}"
    
    if os.path.getsize(file_path) < 1024:
        return False, f"File size too small (< 1KB): {file_path}"
        
    ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,codec_name",
        "-of", "json",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        if not streams:
            return False, f"No video stream found in: {file_path}"
            
        stream = streams[0]
        w = int(stream.get("width", 0))
        h = int(stream.get("height", 0))
        if w <= 0 or h <= 0:
            return False, f"Invalid dimensions {w}x{h} in: {file_path}"
            
        return True, "Valid media asset"
    except Exception as e:
        return False, f"Corrupted or unreadable media asset: {e}"

def validate_video_content(
    video_path: str,
    expected_duration: Optional[float] = None,
    qa_dir: str = "/tmp/auvyra-video-qa",
    min_variance: float = 12.0,
    max_near_black_ratio: float = 0.75
) -> VisualQAReport:
    """Rigorous programmatic visual and audio validation of a rendered video file.
    
    Samples frames at 0%, 10%, 25%, 50%, 75%, 90% and verifies that frames contain
    real visible content, valid audio, synchronization, and lack of blank/black void.
    """
    failure_reasons = []
    
    if not os.path.exists(video_path):
        return VisualQAReport(
            is_valid=False,
            video_path=video_path,
            duration=0,
            width=0,
            height=0,
            fps=0,
            total_frames=0,
            audio_valid=False,
            audio_codec="",
            audio_duration=0,
            audio_mean_volume_db=-999,
            sync_valid=False,
            failure_reasons=[f"File does not exist: {video_path}"],
            qa_artifact_dir=qa_dir
        )
        
    ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    
    # 1. Inspect Video Stream
    cmd_v = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,r_frame_rate,nb_frames,codec_name:format=duration",
        "-of", "json",
        video_path
    ]
    res_v = subprocess.run(cmd_v, capture_output=True, text=True, timeout=30)
    try:
        data_v = json.loads(res_v.stdout)
        v_stream = data_v.get("streams", [{}])[0]
        v_format = data_v.get("format", {})
        
        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
        video_duration = float(v_format.get("duration") or v_stream.get("duration") or 0.0)
        
        # Frame rate parsing
        rate_str = v_stream.get("r_frame_rate", "30/1")
        if "/" in rate_str:
            num, den = rate_str.split("/")
            fps = float(num) / max(1.0, float(den))
        else:
            fps = float(rate_str or 30.0)
            
        nb_frames = int(v_stream.get("nb_frames") or int(video_duration * fps))
    except Exception as e:
        failure_reasons.append(f"Failed to probe video stream: {e}")
        width, height, video_duration, fps, nb_frames = 0, 0, 0.0, 0.0, 0
        
    if width <= 0 or height <= 0:
        failure_reasons.append(f"Invalid video dimensions: {width}x{height}")
    if video_duration <= 0.5:
        failure_reasons.append(f"Video duration too short: {video_duration:.2f}s")
        
    # 2. Inspect Audio Stream
    cmd_a = [
        ffprobe_bin, "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,duration,sample_rate,channels",
        "-of", "json",
        video_path
    ]
    res_a = subprocess.run(cmd_a, capture_output=True, text=True, timeout=30)
    audio_valid = False
    audio_codec = ""
    audio_duration = 0.0
    audio_mean_volume_db = -999.0
    
    try:
        data_a = json.loads(res_a.stdout)
        a_streams = data_a.get("streams", [])
        if a_streams:
            a_stream = a_streams[0]
            audio_codec = a_stream.get("codec_name", "")
            audio_duration = float(a_stream.get("duration") or video_duration)
            audio_valid = bool(audio_codec and audio_duration > 0)
    except Exception as e:
        failure_reasons.append(f"Failed to probe audio stream: {e}")
        
    if not audio_valid:
        failure_reasons.append("Final video missing audio stream or audio duration is 0")
    else:
        # Detect audio volume level using FFmpeg volumedetect filter
        vol_cmd = [
            ffmpeg_bin, "-i", video_path,
            "-af", "volumedetect",
            "-vn", "-sn", "-dn",
            "-f", "null", "-"
        ]
        vol_res = subprocess.run(vol_cmd, capture_output=True, text=True, timeout=30)
        for line in vol_res.stderr.splitlines():
            if "mean_volume:" in line:
                try:
                    audio_mean_volume_db = float(line.split("mean_volume:")[1].split("dB")[0].strip())
                except Exception:
                    pass
        if audio_mean_volume_db <= -70.0:
            failure_reasons.append(f"Audio stream is dead silence (mean volume: {audio_mean_volume_db} dB)")
            audio_valid = False
            
    # 3. Audio/Video Synchronization Check
    sync_valid = True
    if audio_valid and video_duration > 0:
        dur_diff = abs(video_duration - audio_duration)
        if dur_diff > 2.0:
            sync_valid = False
            failure_reasons.append(f"Audio/Video desynchronized: video is {video_duration:.2f}s, audio is {audio_duration:.2f}s (diff: {dur_diff:.2f}s)")
            
    # 4. Sample and inspect representative frames
    os.makedirs(qa_dir, exist_ok=True)
    percentages = [0.05, 0.20, 0.40, 0.60, 0.80, 0.95]
    frame_metrics: List[FrameMetrics] = []
    sampled_arrays: List[np.ndarray] = []

    for p in percentages:
        t = min(video_duration * p, max(0.0, video_duration - 0.1))
        frame_name = f"frame_{int(p*100):02d}.png"
        frame_path = os.path.join(qa_dir, frame_name)

        sample_cmd = [
            ffmpeg_bin, "-y",
            "-ss", f"{t:.3f}",
            "-i", video_path,
            "-vframes", "1",
            frame_path
        ]
        sample_res = subprocess.run(sample_cmd, capture_output=True, timeout=30)

        if not os.path.exists(frame_path) or os.path.getsize(frame_path) == 0:
            failure_reasons.append(f"Failed to capture frame at {int(p*100)}% (t={t:.2f}s)")
            continue

        try:
            img = Image.open(frame_path).convert("RGB")
            arr = np.array(img, dtype=np.float32)
            sampled_arrays.append(arr)

            # Compute luminance using ITU-R BT.601 standard: Y = 0.299*R + 0.587*G + 0.114*B
            lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            mean_lum = float(np.mean(lum))
            pixel_var = float(np.std(lum))

            # Fraction of pixels nearly pitch black (< 12 out of 255)
            near_black = float(np.mean(lum < 12.0))

            # A frame is blank if standard deviation is almost zero or it's almost 100% black
            is_blank = (pixel_var < min_variance) or (near_black > max_near_black_ratio and mean_lum < 15.0)

            metric = FrameMetrics(
                percentage=p,
                timestamp=t,
                frame_path=frame_path,
                mean_luminance=mean_lum,
                pixel_variance=pixel_var,
                near_black_ratio=near_black,
                is_blank=is_blank
            )
            frame_metrics.append(metric)

            if is_blank:
                failure_reasons.append(
                    f"Frame at {int(p*100)}% (t={t:.2f}s) is effectively blank/black: "
                    f"std={pixel_var:.2f} (min {min_variance}), mean_lum={mean_lum:.2f}, near_black={near_black*100:.1f}%"
                )
        except Exception as e:
            failure_reasons.append(f"Error analyzing frame {frame_name}: {e}")

    # 5. Static Placeholder Detection (zero visual motion across timeline)
    if len(sampled_arrays) >= 4 and video_duration >= 5.0:
        static_diffs = []
        for i in range(1, len(sampled_arrays)):
            if sampled_arrays[i].shape == sampled_arrays[i-1].shape:
                diff = float(np.mean(np.abs(sampled_arrays[i] - sampled_arrays[i-1])))
                static_diffs.append(diff)
        if static_diffs and np.mean(static_diffs) < 1.0:
            failure_reasons.append("Static placeholder video detected: zero visual movement across timeline frames")


    # Overall validation judgment
    is_valid = len(failure_reasons) == 0
    
    return VisualQAReport(
        is_valid=is_valid,
        video_path=video_path,
        duration=video_duration,
        width=width,
        height=height,
        fps=fps,
        total_frames=nb_frames,
        audio_valid=audio_valid,
        audio_codec=audio_codec,
        audio_duration=audio_duration,
        audio_mean_volume_db=audio_mean_volume_db,
        sync_valid=sync_valid,
        frame_metrics=frame_metrics,
        failure_reasons=failure_reasons,
        qa_artifact_dir=qa_dir
    )

