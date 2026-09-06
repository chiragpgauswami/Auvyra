import os
import subprocess
import shutil
import json
from loguru import logger

SUPPORTED_CODECS = ["libx264", "h264_nvenc", "h264_amf", "h264_qsv", "h264_videotoolbox"]
DEFAULT_CODEC = "libx264"

def get_ffmpeg_binary() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"

def ffmpeg_encoder_exists(codec: str) -> bool:
    try:
        res = subprocess.run([get_ffmpeg_binary(), "-encoders"], capture_output=True, text=True)
        return codec in res.stdout
    except Exception:
        return False

def get_effective_codec(preferred: str = None) -> str:
    if preferred and preferred in SUPPORTED_CODECS:
        if ffmpeg_encoder_exists(preferred):
            return preferred
    return DEFAULT_CODEC

def write_videofile_with_codec_fallback(clip, output: str, codec: str, **kwargs):
    effective = get_effective_codec(codec)
    try:
        clip.write_videofile(output, codec=effective, **kwargs)
        return effective
    except Exception as e:
        logger.warning(f"Failed with {effective}, falling back to {DEFAULT_CODEC}: {e}")
        clip.write_videofile(output, codec=DEFAULT_CODEC, **kwargs)
        return DEFAULT_CODEC

def concat_clips_with_ffmpeg(clip_files: list[str], output: str, threads: int = 2, max_duration: float = None) -> str:
    list_file = output + ".txt"
    with open(list_file, "w") as f:
        for clip in clip_files:
            f.write(f"file '{os.path.abspath(clip)}'\n")
            
    cmd = [
        get_ffmpeg_binary(), "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output
    ]
    subprocess.run(cmd, check=True)
    os.remove(list_file)
    return output

def probe_video_info(file_path: str) -> dict:
    try:
        cmd = [
            shutil.which("ffprobe") or "ffprobe",
            "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", file_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(res.stdout)
        
        duration = float(data.get("format", {}).get("duration", 0))
        size = int(data.get("format", {}).get("size", 0))
        
        width = 0
        height = 0
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                break
                
        return {"duration": duration, "size": size, "width": width, "height": height}
    except Exception:
        return {}
