import os
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip
from loguru import logger
from ..models import VideoGenerationRequest
from ..rendering.ffmpeg import write_videofile_with_codec_fallback
from ..subtitles.srt_parser import parse_srt

class VideoOverlay:
    def compose_final(self, video_path: str, audio_path: str, subtitle_path: str | None, 
                      output_path: str, params: VideoGenerationRequest) -> bool:
        try:
            with VideoFileClip(video_path) as video:
                with AudioFileClip(audio_path) as audio:
                    # Match video duration to narration audio
                    video = video.subclipped(0, min(video.duration, audio.duration))
                    video = video.with_audio(audio)
                    
                    sub_clips = []
                    
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
                                font_size=max(26, int(params.font_size * 0.52)),
                                color="#38BDF8",  # Vibrant cyan
                                bg_color=(15, 23, 42, 220),  # Dark translucent pill
                                margin=(28, 12),
                                text_align="center"
                            )
                            .with_start(0)
                            .with_end(video.duration)
                            .with_duration(video.duration)
                            .with_position(("center", int(video.size[1] * 0.06)))
                        )
                        sub_clips.append(header_clip)
                    except Exception as h_err:
                        logger.warning(f"Failed to render header badge: {h_err}")

                    # 2. Overlay subtitles if enabled
                    if subtitle_path and os.path.exists(subtitle_path) and getattr(params, "subtitle_enabled", True):
                        srt_entries = parse_srt(subtitle_path)
                        target_width = int(video.size[0] * 0.88)
                        
                        for idx, (start_sec, end_sec), text in srt_entries:
                            duration = max(0.1, end_sec - start_sec)
                            if start_sec >= video.duration:
                                continue
                            try:
                                txt_clip = (
                                    TextClip(
                                        text=text,
                                        font_size=params.font_size or 54,
                                        color=params.text_color or "#FFFFFF",
                                        stroke_color=params.stroke_color or "#000000",
                                        stroke_width=int(params.stroke_width or 2),
                                        bg_color=(0, 0, 0, 180),
                                        margin=(24, 14),
                                        size=(target_width, None),
                                        text_align="center"
                                    )
                                    .with_start(start_sec)
                                    .with_end(min(end_sec, video.duration))
                                    .with_duration(duration)
                                    .with_position(("center", int(video.size[1] * 0.72)))
                                )
                                sub_clips.append(txt_clip)
                            except Exception as txt_err:
                                logger.warning(f"Failed to render subtitle text '{text}': {txt_err}")
                                
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
