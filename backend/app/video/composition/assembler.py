import os
import math
from typing import List
from moviepy import VideoFileClip, CompositeVideoClip, ColorClip
from ..models import VideoAspect
from ..rendering.ffmpeg import concat_clips_with_ffmpeg

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
    else: # contain / letterbox
        scale_factor = min(width_scale, height_scale)
        resized_width = max(1, min(target_width, int(source_width * scale_factor)))
        resized_height = max(1, min(target_height, int(source_height * scale_factor)))
        resized_clip = clip.resized(new_size=(resized_width, resized_height)).with_position("center")
        bg = ColorClip(size=(target_width, target_height), color=(0, 0, 0)).with_duration(clip.duration)
        return CompositeVideoClip([bg, resized_clip], size=(target_width, target_height)).with_duration(clip.duration)

class VideoAssembler:
    def assemble_clips(self, video_paths: List[str], audio_duration: float, 
                       aspect_ratio: VideoAspect, output_path: str, 
                       max_clip_duration: int = 5, fit_mode: str = "cover") -> str:
        
        target_width, target_height = aspect_ratio.to_resolution()
        required_duration = audio_duration + 0.5
        
        temp_dir = os.path.dirname(output_path)
        processed_paths = []
        current_duration = 0.0
        
        idx = 0
        while current_duration < required_duration:
            for v_path in video_paths:
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
                        
                        current_duration += clip_dur
                        idx += 1
                except Exception as e:
                    print(f"Error processing clip {v_path}: {e}")
                    
        concat_clips_with_ffmpeg(processed_paths, output_path)
        
        # Cleanup temp clips
        for p in processed_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
                
        return output_path
