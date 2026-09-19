import os
import math
from typing import List, Any, Optional, Dict, Tuple
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip
from ..models import VideoAspect
from ..rendering.ffmpeg import concat_clips_with_ffmpeg
from ..validation import validate_media_asset

def fit_clip_to_canvas(clip, target_width: int, target_height: int, fit_mode: str = "cover"):
    """Resize and crop/letterbox a clip to exact canvas dimensions using MoviePy 2.x."""
    source_width, source_height = int(clip.size[0]), int(clip.size[1])
    if (source_width, source_height) == (target_width, target_height):
        return clip

    width_scale = target_width / source_width
    height_scale = target_height / source_height

    if fit_mode == "cover":
        scale_factor = max(width_scale, height_scale)
        resized_width = max(target_width, math.ceil(source_width * scale_factor))
        resized_height = max(target_height, math.ceil(source_height * scale_factor))
        resized_clip = clip.resized(new_size=(resized_width, resized_height))
        crop_x = max(0, (resized_width - target_width) // 2)
        crop_y = max(0, (resized_height - target_height) // 2)
        return resized_clip.cropped(
            x1=crop_x,
            y1=crop_y,
            width=target_width,
            height=target_height,
        )
    else:  # contain / letterbox
        scale_factor = min(width_scale, height_scale)
        resized_width = max(1, min(target_width, int(source_width * scale_factor)))
        resized_height = max(1, min(target_height, int(source_height * scale_factor)))
        resized_clip = clip.resized(new_size=(resized_width, resized_height)).with_position("center")
        bg = ColorClip(size=(target_width, target_height), color=(0, 0, 0)).with_duration(clip.duration)
        return CompositeVideoClip([bg, resized_clip], size=(target_width, target_height)).with_duration(clip.duration)

def calculate_interval_union_coverage(
    intervals: List[Tuple[float, float]],
    total_duration: float
) -> Tuple[float, float]:
    """
    Computes true unique timeline coverage using the mathematical union of intervals.
    Prevents artificial inflation from simply summing clip durations.
    Returns: (total_union_duration, coverage_ratio)
    """
    if not intervals or total_duration <= 0:
        return 0.0, 0.0

    valid_intervals = [
        (max(0.0, float(s)), min(float(total_duration), float(e)))
        for s, e in intervals
        if e > s
    ]
    if not valid_intervals:
        return 0.0, 0.0

    sorted_intervals = sorted(valid_intervals, key=lambda x: x[0])
    merged = []
    for s, e in sorted_intervals:
        if not merged:
            merged.append([s, e])
        else:
            prev_s, prev_e = merged[-1]
            if s <= prev_e:
                merged[-1][1] = max(prev_e, e)
            else:
                merged.append([s, e])

    union_dur = sum(e - s for s, e in merged)
    ratio = min(1.0, union_dur / float(total_duration))
    return round(union_dur, 3), round(ratio, 4)


class VideoAssembler:
    """Assembles and stitches stock footage clips with interval-union timeline coverage validation."""

    def __init__(self):
        self.last_coverage_report: Dict[str, Any] = {}

    def assemble_clips(
        self,
        video_paths: List[str],
        audio_duration: float,
        aspect_ratio: VideoAspect,
        output_path: str,
        max_clip_duration: int = 5,
        fit_mode: str = "cover"
    ) -> str:
        target_width, target_height = aspect_ratio.to_resolution()
        required_duration = audio_duration + 0.5

        # Filter and validate all incoming video paths
        valid_video_paths = []
        for v in video_paths:
            is_valid, msg = validate_media_asset(v)
            if is_valid:
                valid_video_paths.append(v)
            else:
                print(f"Skipping invalid source clip {v}: {msg}")

        if not valid_video_paths:
            raise RuntimeError(f"No valid video source assets available to assemble video. Input paths were: {video_paths}")

        temp_dir = os.path.dirname(output_path)
        processed_paths = []
        timeline_intervals = []
        current_duration = 0.0

        idx = 0
        while current_duration < required_duration:
            for v_path in valid_video_paths:
                if current_duration >= required_duration:
                    break

                try:
                    with VideoFileClip(v_path) as clip:
                        clip_dur = min(clip.duration, float(max_clip_duration))
                        subclip = clip.subclipped(0, clip_dur)
                        fitted = fit_clip_to_canvas(subclip, target_width, target_height, fit_mode=fit_mode)

                        temp_file = os.path.join(temp_dir, f"clip_{idx}.mp4")
                        fitted.write_videofile(temp_file, codec="libx264", audio=False, logger=None)
                        processed_paths.append(temp_file)

                        clip_start = current_duration
                        clip_end = current_duration + clip_dur
                        timeline_intervals.append((clip_start, clip_end))

                        current_duration += clip_dur
                        idx += 1
                except Exception as e:
                    print(f"Error processing clip {v_path}: {e}")

        concat_clips_with_ffmpeg(processed_paths, output_path)

        # Compute interval union coverage
        union_dur, ratio = calculate_interval_union_coverage(timeline_intervals, audio_duration)
        self.last_coverage_report = {
            "union_duration": union_dur,
            "coverage_ratio": ratio,
            "total_clips": len(processed_paths),
            "timeline_intervals": timeline_intervals
        }

        # Cleanup temp clips
        for p in processed_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        return output_path

    def assemble_storyboard_scenes(
        self,
        storyboard_scenes: List[Any],
        media_items: List[Any],
        audio_duration: float,
        aspect_ratio: VideoAspect,
        output_path: str,
        fit_mode: str = "cover"
    ) -> str:
        """Assembles scene-by-scene stock footage aligned to the storyboard timeline."""
        target_width, target_height = aspect_ratio.to_resolution()
        required_duration = audio_duration + 0.5
        temp_dir = os.path.dirname(output_path)
        processed_paths = []
        timeline_intervals = []
        current_duration = 0.0

        # Map scene_index to media items
        media_by_scene = {}
        for m in media_items:
            path = getattr(m, "local_path", str(m))
            is_valid, _ = validate_media_asset(path)
            if is_valid:
                s_idx = getattr(m, "scene_index", None)
                if s_idx is not None:
                    media_by_scene[s_idx] = path

        # Fallback pool if a scene doesn't have an exact match
        valid_pool = list(media_by_scene.values())
        if not valid_pool:
            for m in media_items:
                path = getattr(m, "local_path", str(m))
                is_valid, _ = validate_media_asset(path)
                if is_valid:
                    valid_pool.append(path)

        if not valid_pool:
            raise RuntimeError("No valid video clips available to assemble storyboard scenes.")

        scene_idx = 0
        loop_guard = 0
        last_used_clip = None

        while current_duration < required_duration and loop_guard < 50:
            loop_guard += 1
            for s in storyboard_scenes:
                if current_duration >= required_duration:
                    break

                s_id = getattr(s, "scene_index", scene_idx + 1)
                clip_path = media_by_scene.get(s_id)

                # Avoid duplicate consecutive clips if pool has > 1 clip
                if not clip_path or (clip_path == last_used_clip and len(valid_pool) > 1):
                    alt_clips = [p for p in valid_pool if p != last_used_clip]
                    clip_path = alt_clips[scene_idx % len(alt_clips)] if alt_clips else valid_pool[0]

                target_dur = float(getattr(s, "duration", 3.0))

                try:
                    with VideoFileClip(clip_path) as clip:
                        clip_dur = min(clip.duration, target_dur)
                        if clip_dur <= 0.1:
                            clip_dur = target_dur
                        subclip = clip.subclipped(0, min(clip.duration, clip_dur))
                        fitted = fit_clip_to_canvas(subclip, target_width, target_height, fit_mode=fit_mode)

                        temp_file = os.path.join(temp_dir, f"scene_clip_{scene_idx}.mp4")
                        fitted.write_videofile(temp_file, codec="libx264", audio=False, logger=None)
                        processed_paths.append(temp_file)

                        clip_start = current_duration
                        clip_end = current_duration + clip_dur
                        timeline_intervals.append((clip_start, clip_end))

                        current_duration += clip_dur
                        last_used_clip = clip_path
                        scene_idx += 1
                except Exception as e:
                    print(f"Error processing scene {s_id} clip {clip_path}: {e}")

        if not processed_paths:
            raise RuntimeError("Failed to process any scene clips.")

        concat_clips_with_ffmpeg(processed_paths, output_path)

        # Compute interval union coverage
        union_dur, ratio = calculate_interval_union_coverage(timeline_intervals, audio_duration)
        self.last_coverage_report = {
            "union_duration": union_dur,
            "coverage_ratio": ratio,
            "total_scenes": len(processed_paths),
            "timeline_intervals": timeline_intervals
        }

        for p in processed_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

        return output_path
