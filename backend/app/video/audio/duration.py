import subprocess
import shutil

def get_ffmpeg_binary() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"
    
def get_ffprobe_binary() -> str:
    return shutil.which("ffprobe") or "ffprobe"

def get_audio_duration(file_path: str) -> float:
    try:
        cmd = [
            get_ffprobe_binary(),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        # Fallback to moviepy
        try:
            from moviepy.audio.io.AudioFileClip import AudioFileClip
            with AudioFileClip(file_path) as clip:
                return clip.duration
        except Exception:
            return 0.0
