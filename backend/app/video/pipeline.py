import os
import tempfile
from typing import Callable, Optional
from loguru import logger

from .models import VideoGenerationRequest, VideoGenerationResult, PipelineProgress, VideoAspect
from .tasks.manager import VideoTaskManager
from .media.pexels_provider import PexelsProvider
from .media.pexels_stock_service import PexelsStockService
from .media.local_provider import LocalMediaProvider
from .storyboard import StoryboardGenerator
from .audio.edge_tts_provider import EdgeTTSProvider
from .audio.duration import get_audio_duration
from .subtitles.generator import SubtitleGenerator
from .composition.assembler import VideoAssembler
from .composition.overlay import VideoOverlay
from .rendering.ffmpeg import probe_video_info
from .validation import validate_video_content

class VideoGenerationService:
    """Clean interface for video generation with scene-by-scene storyboard stock footage."""
    
    def __init__(self, ai_client=None, media_provider=None, tts_provider=None, settings=None):
        self.ai_client = ai_client
        self.media_provider = media_provider
        self.tts_provider = tts_provider or EdgeTTSProvider()
        self.settings = settings or {}
    
    def _resolve_media_provider(self, request: VideoGenerationRequest):
        if self.media_provider:
            return self.media_provider
        
        pexels_key = os.getenv("PEXELS_API_KEY", "")
        if request.video_source == "local" or not pexels_key:
            logger.info("Using LocalMediaProvider (local-first mode)")
            return LocalMediaProvider()
        
        logger.info("Using PexelsStockService")
        return PexelsStockService(api_keys=pexels_key)

    async def generate(self, request: VideoGenerationRequest, 
                       progress_callback: Optional[Callable[[PipelineProgress], None]] = None) -> VideoGenerationResult:
        """Execute the full video generation pipeline."""
        task_manager = VideoTaskManager(progress_callback)
        
        # 1. Initialize (0%)
        task_manager.report_progress(*task_manager.INITIALIZING, "Setting up working directory")
        output_dir = request.output_dir or tempfile.mkdtemp(prefix="auvyra_video_")
        os.makedirs(output_dir, exist_ok=True)
        
        # 2. Generate script assets & visual storyboard (10%)
        task_manager.report_progress(*task_manager.SCRIPT_ASSETS, "Generating scene-by-scene visual storyboard")
        script = (request.script or "").strip()
        if not script:
            script = "Exploring the top tools in artificial intelligence. From automated creativity to intelligent workflows, modern AI is transforming how we build."
            
        storyboard_gen = StoryboardGenerator(ai_gateway=self.ai_client)
        storyboard = await storyboard_gen.generate_storyboard(
            script=script,
            total_duration=float(request.duration),
            topic=request.topic,
            aspect_ratio=request.aspect_ratio
        )
        logger.info(f"Generated storyboard with {len(storyboard.scenes)} scenes (total {storyboard.total_duration:.1f}s)")
            
        # 3. Find and download stock media per scene (25%)
        task_manager.report_progress(*task_manager.FINDING_MEDIA, f"Sourcing stock footage for {len(storyboard.scenes)} scenes")
        aspect = VideoAspect(request.aspect_ratio)
        pexels_key = os.getenv("PEXELS_API_KEY", "")
        
        media_items = []
        if pexels_key and request.video_source != "local":
            try:
                stock_service = PexelsStockService(api_keys=pexels_key)
                media_items = await stock_service.fetch_media_for_storyboard(
                    storyboard=storyboard,
                    dest_dir=output_dir,
                    aspect_ratio=aspect
                )
            except Exception as e:
                logger.error(f"Pexels storyboard fetch failed: {e}")
                raise RuntimeError(f"PEXELS_NO_SUITABLE_MEDIA: {e}")

        if not media_items and request.video_source == "pexels":
            raise RuntimeError("PEXELS_NO_SUITABLE_MEDIA: No suitable stock video clips could be retrieved for storyboard scenes")

        if not media_items and request.video_source == "local":
            # Local media provider explicitly requested
            logger.info("Local video source requested, using LocalMediaProvider")
            local_fallback = LocalMediaProvider()
            search_terms = [request.topic]
            media_items = await local_fallback.search_and_download(
                queries=search_terms,
                dest_dir=output_dir,
                aspect_ratio=aspect,
                target_duration=request.duration
            )

        if not media_items:
            raise RuntimeError("PEXELS_NO_SUITABLE_MEDIA: Failed to find or generate suitable video media for the timeline")
            
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
        task_manager.report_progress(*task_manager.COMPOSING_VIDEO, "Composing multi-clip video scenes and timing")
        assembler = VideoAssembler()
        assembled_video_path = os.path.join(output_dir, "assembled.mp4")
        
        has_storyboard_scenes = storyboard and storyboard.scenes and any(hasattr(m, "scene_index") and m.scene_index is not None for m in media_items)
        if has_storyboard_scenes:
            assembled_video_path = assembler.assemble_storyboard_scenes(
                storyboard_scenes=storyboard.scenes,
                media_items=media_items,
                audio_duration=audio_duration,
                aspect_ratio=aspect,
                output_path=assembled_video_path,
                fit_mode="cover"
            )
        else:
            paths = [m.local_path if hasattr(m, "local_path") else str(m) for m in media_items]
            assembled_video_path = assembler.assemble_clips(
                video_paths=paths,
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
            
        # 8. Complete (100%) - Programmatic Visual QA
        task_manager.report_progress(*task_manager.COMPLETED, "Video generation successfully completed")
        
        qa_report = validate_video_content(final_video_path, expected_duration=audio_duration)
        if not qa_report.is_valid:
            logger.warning(f"Visual QA warnings on output video: {qa_report.failure_reasons}")
        else:
            logger.info("Visual QA PASSED: Real stock video frames, valid audio, no black/void void.")

        info = probe_video_info(final_video_path)
        target_w, target_h = aspect.to_resolution()
        
        return VideoGenerationResult(
            video_path=final_video_path,
            duration=info.get("duration", audio_duration),
            width=info.get("width", target_w),
            height=info.get("height", target_h),
            size_bytes=info.get("size", os.path.getsize(final_video_path)),
            subtitle_path=subtitle_path,
            audio_path=audio_path,
            media_items=media_items,
            storyboard=storyboard
        )
