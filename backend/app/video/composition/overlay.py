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
                    # Overlay subtitles if enabled
                    if subtitle_path and os.path.exists(subtitle_path) and getattr(params, "subtitle_enabled", True):
                        srt_entries = parse_srt(subtitle_path)
                        target_width = int(video.size[0] * 0.9)
                        
                        for idx, (start_sec, end_sec), text in srt_entries:
                            duration = max(0.1, end_sec - start_sec)
                            if start_sec >= video.duration:
                                continue
                            try:
                                txt_clip = (
                                    TextClip(
                                        text=text,
                                        font_size=params.font_size,
                                        color=params.text_color,
                                        stroke_color=params.stroke_color,
                                        stroke_width=int(params.stroke_width or 1),
                                        size=(target_width, None),
                                        text_align="center"
                                    )
                                    .with_start(start_sec)
                                    .with_end(min(end_sec, video.duration))
                                    .with_duration(duration)
                                    .with_position(("center", int(video.size[1] * 0.78)))
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
