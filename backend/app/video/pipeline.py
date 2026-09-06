import os
import tempfile
from typing import Callable, Optional
from loguru import logger

from .models import VideoGenerationRequest, VideoGenerationResult, PipelineProgress, VideoAspect
from .tasks.manager import VideoTaskManager
from .media.pexels_provider import PexelsProvider
from .media.local_provider import LocalMediaProvider
from .audio.edge_tts_provider import EdgeTTSProvider
from .audio.duration import get_audio_duration
from .subtitles.generator import SubtitleGenerator
from .composition.assembler import VideoAssembler
from .composition.overlay import VideoOverlay
from .rendering.ffmpeg import probe_video_info

class VideoGenerationService:
    """Clean interface for video generation.
    The rest of Auvyra must not know whether the implementation comes from
    MoneyPrinterTurbo, Auvyra-native code, or another future engine."""
    
    def __init__(self, ai_client=None, media_provider=None, tts_provider=None, settings=None):
        self.ai_client = ai_client
        self.media_provider = media_provider
        self.tts_provider = tts_provider or EdgeTTSProvider()
        self.settings = settings or {}
    
    def _resolve_media_provider(self, request: VideoGenerationRequest):
        if self.media_provider:
            return self.media_provider
        
        # If explicitly local or no Pexels API key configured, use LocalMediaProvider
        pexels_key = os.getenv("PEXELS_API_KEY", "")
        if request.video_source == "local" or not pexels_key:
            logger.info("Using LocalMediaProvider (local-first mode)")
            return LocalMediaProvider()
        
        logger.info("Using PexelsProvider")
        return PexelsProvider(api_keys=pexels_key)

    async def generate(self, request: VideoGenerationRequest, 
                       progress_callback: Optional[Callable[[PipelineProgress], None]] = None) -> VideoGenerationResult:
        """Execute the full video generation pipeline."""
        task_manager = VideoTaskManager(progress_callback)
        
        # 1. Initialize (0%)
        task_manager.report_progress(*task_manager.INITIALIZING, "Setting up working directory")
        output_dir = request.output_dir or tempfile.mkdtemp(prefix="auvyra_video_")
        os.makedirs(output_dir, exist_ok=True)
        
        # 2. Generate script assets (10%)
        task_manager.report_progress(*task_manager.SCRIPT_ASSETS, "Preparing script and visual search terms")
        script = (request.script or "").strip()
        if not script:
            script = f"Exploring the top tools in artificial intelligence. From automated creativity to intelligent workflows, modern AI is transforming how we build."
            
        search_terms = [word for word in request.topic.split() if len(word) > 3]
        if not search_terms:
            search_terms = ["technology", "digital", "future"]
            
        # 3. Find media (25%)
        task_manager.report_progress(*task_manager.FINDING_MEDIA, "Finding and selecting media assets")
        aspect = VideoAspect(request.aspect_ratio)
        provider = self._resolve_media_provider(request)
        media_items = await provider.search_and_download(
            queries=search_terms, 
            dest_dir=output_dir,
            aspect_ratio=aspect,
            target_duration=request.duration
        )
        
        if not media_items:
            # Fallback to local media provider if online provider failed or returned empty
            logger.warning("Media search returned empty, falling back to LocalMediaProvider")
            local_fallback = LocalMediaProvider()
            media_items = await local_fallback.search_and_download(
                queries=search_terms,
                dest_dir=output_dir,
                aspect_ratio=aspect,
                target_duration=request.duration
            )
            
        if not media_items:
            raise RuntimeError("Failed to find or generate suitable video media")
            
        # 4. Generate narration (40%)
        task_manager.report_progress(*task_manager.GENERATING_NARRATION, "Synthesizing voice narration")
        audio_path = os.path.join(output_dir, "narration.mp3")
        tts_result = await self.tts_provider.synthesize(
            text=script,
            voice_name=request.voice_name,
            voice_rate=request.voice_rate,
            output_path=audio_path
        )
        audio_duration = tts_result.duration
        if audio_duration <= 0:
            audio_duration = get_audio_duration(audio_path)
            
        # 5. Generate subtitles (55%)
        task_manager.report_progress(*task_manager.GENERATING_SUBTITLES, "Generating and aligning subtitles")
        subtitle_path = os.path.join(output_dir, "subtitles.srt")
        subtitle_generator = SubtitleGenerator()
        if tts_result.subtitle_data:
            subtitle_generator.create_from_tts(tts_result.subtitle_data, script, subtitle_path)
        else:
            subtitle_generator.create_from_audio(audio_path, subtitle_path)
            
        # 6. Compose video (70%)
        task_manager.report_progress(*task_manager.COMPOSING_VIDEO, "Composing video clips and timing")
        assembler = VideoAssembler()
        assembled_video_path = os.path.join(output_dir, "assembled.mp4")
        assembled_video_path = assembler.assemble_clips(
            video_paths=media_items,
            audio_duration=audio_duration,
            aspect_ratio=aspect,
            output_path=assembled_video_path,
            max_clip_duration=request.max_clip_duration,
            fit_mode="cover"
        )
        
        # 7. Render (90%)
        task_manager.report_progress(*task_manager.RENDERING, "Rendering final video with FFmpeg")
        overlay = VideoOverlay()
        final_video_path = os.path.join(output_dir, "example.mp4")
        success = overlay.compose_final(
            video_path=assembled_video_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path if request.subtitle_enabled else None,
            output_path=final_video_path,
            params=request
        )
        
        if not success or not os.path.exists(final_video_path):
            raise RuntimeError("Final rendering failed")
            
        # 8. Complete (100%)
        task_manager.report_progress(*task_manager.COMPLETED, "Video generation successfully completed")
        
        info = probe_video_info(final_video_path)
        target_w, target_h = aspect.to_resolution()
        
        return VideoGenerationResult(
            video_path=final_video_path,
            duration=info.get("duration", audio_duration),
            width=info.get("width", target_w),
            height=info.get("height", target_h),
            size_bytes=info.get("size", os.path.getsize(final_video_path)),
            subtitle_path=subtitle_path,
            audio_path=audio_path
        )
