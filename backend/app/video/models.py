from pydantic import BaseModel, Field
from enum import Enum
from typing import Callable, Any

class VideoAspect(str, Enum):
    landscape = "16:9"
    portrait = "9:16"
    square = "1:1"
    
    def to_resolution(self) -> tuple[int, int]:
        if self == VideoAspect.landscape: return (1920, 1080)
        elif self == VideoAspect.portrait: return (1080, 1920)
        elif self == VideoAspect.square: return (1080, 1080)
        raise ValueError(f"unsupported aspect: {self}")

class VideoFitMode(str, Enum):
    cover = "cover"
    contain = "contain"

class MediaItem(BaseModel):
    provider: str = "pexels"
    url: str = ""
    local_path: str = ""
    duration: float = 0
    width: int = 0
    height: int = 0
    search_term: str = ""

class TTSResult(BaseModel):
    audio_path: str
    duration: float
    subtitle_data: Any = None  # SubMaker or word timestamps

class PipelineProgress(BaseModel):
    stage: str
    percent: int
    message: str

class VideoGenerationRequest(BaseModel):
    topic: str
    script: str = ""
    duration: int = 45
    aspect_ratio: str = "9:16"
    voice_name: str = "en-US-AriaNeural-Female"
    voice_rate: float = 1.0
    subtitle_enabled: bool = True
    font_size: int = 60
    text_color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: float = 1.5
    bgm_type: str = "random"  # random, none, or file path
    bgm_volume: float = 0.2
    video_source: str = "pexels"  # pexels, local
    max_clip_duration: int = 5
    video_count: int = 1
    output_dir: str = ""

class VideoGenerationResult(BaseModel):
    video_path: str
    duration: float
    width: int
    height: int
    size_bytes: int
    subtitle_path: str | None = None
    audio_path: str | None = None
