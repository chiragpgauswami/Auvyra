from typing import Callable, Optional
from ..models import PipelineProgress

class VideoTaskManager:
    INITIALIZING = ("initializing", 0)
    SCRIPT_ASSETS = ("script_assets", 10)
    FINDING_MEDIA = ("finding_media", 25)
    GENERATING_NARRATION = ("generating_narration", 40)
    GENERATING_SUBTITLES = ("generating_subtitles", 55)
    COMPOSING_VIDEO = ("composing_video", 70)
    RENDERING = ("rendering", 90)
    COMPLETED = ("completed", 100)
    
    def __init__(self, callback: Optional[Callable[[PipelineProgress], None]]):
        self.callback = callback
        
    def report_progress(self, stage: str, percent: int, message: str):
        if self.callback:
            self.callback(PipelineProgress(stage=stage, percent=percent, message=message))
