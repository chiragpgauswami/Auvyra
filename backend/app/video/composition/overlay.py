import os
from typing import Optional, Tuple, List
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
from loguru import logger
from ..models import VideoGenerationRequest
from ..rendering.ffmpeg import write_videofile_with_codec_fallback
from ..subtitles.srt_parser import parse_srt

def resolve_platform_font(preferred_font: Optional[str] = None) -> Optional[str]:
    """
    Resolves bold, high-retention typography across macOS, Linux (Debian/Ubuntu), and Windows.
    Returns path or font family name recognized by MoviePy / ImageMagick / PIL.
    """
    if preferred_font and os.path.exists(preferred_font):
        return preferred_font

    candidates = [
        preferred_font,
        # macOS system fonts
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Linux standard truetype fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        # Cross-platform font families
        "Montserrat-Black",
        "Arial-Bold",
        "Helvetica-Bold",
        "DejaVuSans-Bold",
        "Impact",
        "Arial",
    ]

    for c in candidates:
        if not c:
            continue
        if os.path.isabs(c):
            if os.path.exists(c):
                return c
        else:
            # Check font family capability
            return c

    return None

def compute_safe_zone_position(
    clip_height: int,
    video_height: int,
    safe_min_ratio: float = 0.62,
    safe_max_ratio: float = 0.76,
    target_ratio: float = 0.70
) -> Tuple[int, float, float]:
    """
    Computes Y position of the caption bounding box such that:
    safe_min_ratio * H <= top_y and bottom_y <= safe_max_ratio * H
    with nominal vertical center at target_ratio * H.
    
    Returns:
        (y_pos_px, actual_top_ratio, actual_bottom_ratio)
    """
    H = float(video_height)
    safe_min_px = safe_min_ratio * H
    safe_max_px = safe_max_ratio * H
    available_h = safe_max_px - safe_min_px

    # If clip exceeds safe zone, it should be adjusted upstream by font scaling
    target_center_px = target_ratio * H
    y_pos = target_center_px - (clip_height / 2.0)

    # Clamp bounding box strictly inside safe zone
    if y_pos < safe_min_px:
        y_pos = safe_min_px
    if (y_pos + clip_height) > safe_max_px:
        y_pos = max(safe_min_px, safe_max_px - clip_height)

    top_ratio = y_pos / H
    bottom_ratio = (y_pos + clip_height) / H
    return int(round(y_pos)), top_ratio, bottom_ratio


class VideoOverlay:
    """Composes narration, audio, branded header, and dynamic safe-zone Shorts captions."""

    def compose_final(
        self,
        video_path: str,
        audio_path: str,
        subtitle_path: Optional[str],
        output_path: str,
        params: VideoGenerationRequest
    ) -> bool:
        try:
            with VideoFileClip(video_path) as video:
                with AudioFileClip(audio_path) as audio:
                    # Match video duration to narration audio
                    video = video.subclipped(0, min(video.duration, audio.duration))
                    video = video.with_audio(audio)
                    v_w, v_h = int(video.size[0]), int(video.size[1])

                    sub_clips = []
                    font_resolved = resolve_platform_font()

                    # 1. Overlay persistent branded header badge at top
                    topic_text = getattr(params, "topic", "") or "AUVYRA PRODUCTION"
                    clean_topic = topic_text.strip().upper()
                    if len(clean_topic) > 36:
                        clean_topic = clean_topic[:33] + "..."
                    header_text = f"● AUVYRA  |  {clean_topic}"

                    try:
                        header_clip = (
                            TextClip(
                                text=header_text,
                                font=font_resolved,
                                font_size=max(24, int(params.font_size * 0.48)),
                                color="#38BDF8",  # Vibrant cyan accent
                                bg_color=(15, 23, 42, 220),  # Dark translucent pill
                                margin=(28, 12),
                                text_align="center"
                            )
                            .with_start(0)
                            .with_end(video.duration)
                            .with_duration(video.duration)
                            .with_position(("center", int(v_h * 0.055)))
                        )
                        sub_clips.append(header_clip)
                    except Exception as h_err:
                        logger.warning(f"Failed to render header badge: {h_err}")

                    # 2. Overlay high-retention subtitles inside strict safe zone (62% - 76%)
                    if subtitle_path and os.path.exists(subtitle_path) and getattr(params, "subtitle_enabled", True):
                        srt_entries = parse_srt(subtitle_path)
                        target_width = int(v_w * 0.86)
                        safe_zone_max_h = int((0.76 - 0.62) * v_h)  # max allowable height for safe zone

                        # Extract caption style configuration if present
                        caption_cfg = getattr(params, "caption_style", None) or {}
                        if isinstance(caption_cfg, dict) and caption_cfg:
                            pref_font = caption_cfg.get("font_family")
                            if pref_font:
                                font_resolved = resolve_platform_font(pref_font) or font_resolved

                            base_font_size = int(caption_cfg.get("font_size", params.font_size or 54))
                            text_color = caption_cfg.get("text_color", params.text_color or "#FFFFFF")
                            stroke_color = caption_cfg.get("stroke_color", params.stroke_color or "#000000")
                            stroke_width = int(round(float(caption_cfg.get("outline_width", params.stroke_width or 2))))

                            bg_type = caption_cfg.get("background_type", "pill")
                            bg_opacity = float(caption_cfg.get("background_opacity", 0.82))
                            if bg_type == "none":
                                bg_color = None
                                clip_margin = None
                            elif bg_type == "box":
                                bg_color = (15, 23, 42, int(round(255 * bg_opacity)))
                                clip_margin = (14, 8)
                            else:  # pill default
                                bg_color = (15, 23, 42, int(round(255 * bg_opacity)))
                                clip_margin = (22, 12)

                            pos_mode = caption_cfg.get("position", "safe_center")
                            if pos_mode == "lower_third":
                                target_ratio = 0.74
                            elif pos_mode == "upper_third":
                                target_ratio = 0.65
                            else:
                                target_ratio = 0.70
                        else:
                            base_font_size = int(params.font_size or 54)
                            text_color = params.text_color or "#FFFFFF"
                            stroke_color = params.stroke_color or "#000000"
                            stroke_width = int(params.stroke_width or 2)
                            bg_color = (15, 23, 42, 210)
                            clip_margin = (22, 12)
                            target_ratio = 0.70

                        for idx, (start_sec, end_sec), text in srt_entries:
                            duration = max(0.12, end_sec - start_sec)
                            if start_sec >= video.duration:
                                continue

                            cue_text = text.strip().upper()
                            if not cue_text:
                                continue

                            # Dynamic font scaling to guarantee bounding box fits safe zone
                            current_font_size = base_font_size
                            txt_clip = None

                            for attempt in range(4):
                                try:
                                    txt_clip_kwargs = {
                                        "text": cue_text,
                                        "font": font_resolved,
                                        "font_size": current_font_size,
                                        "color": text_color,
                                        "stroke_color": stroke_color,
                                        "stroke_width": stroke_width,
                                        "size": (target_width, None),
                                        "text_align": "center"
                                    }
                                    if bg_color:
                                        txt_clip_kwargs["bg_color"] = bg_color
                                    if clip_margin:
                                        txt_clip_kwargs["margin"] = clip_margin

                                    txt_clip = TextClip(**txt_clip_kwargs)
                                    clip_h = int(txt_clip.size[1])
                                    if clip_h <= safe_zone_max_h or current_font_size <= 32:
                                        break
                                    current_font_size = int(current_font_size * 0.85)
                                except Exception as txt_build_err:
                                    logger.warning(f"TextClip build attempt error for '{cue_text}': {txt_build_err}")
                                    break

                            if txt_clip:
                                clip_h = int(txt_clip.size[1])
                                y_pos, top_r, bot_r = compute_safe_zone_position(
                                    clip_height=clip_h,
                                    video_height=v_h,
                                    safe_min_ratio=0.62,
                                    safe_max_ratio=0.76,
                                    target_ratio=target_ratio
                                )

                                final_txt_clip = (
                                    txt_clip
                                    .with_start(start_sec)
                                    .with_end(min(end_sec, video.duration))
                                    .with_duration(duration)
                                    .with_position(("center", y_pos))
                                )
                                sub_clips.append(final_txt_clip)


                    if sub_clips:
                        composite = CompositeVideoClip([video, *sub_clips], size=video.size).with_duration(video.duration)
                    else:
                        composite = video

                    write_videofile_with_codec_fallback(
                        composite,
                        output_path,
                        codec="libx264",
                        audio_codec="aac",
                        fps=30,
                        logger=None
                    )

            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            logger.error(f"Error composing final video: {e}")
            return False
