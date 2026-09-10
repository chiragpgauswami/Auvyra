import os
from typing import Dict, List, Optional, Any, Callable
from loguru import logger
from backend.app.ai.gateway import AIGateway
from backend.app.video.pipeline import VideoGenerationService
from backend.app.video.models import VideoGenerationRequest, VideoGenerationResult, PipelineProgress
from backend.app.repositories.videos import VideoRepository, VideoAssetRepository
from backend.app.repositories.jobs import JobRepository
from backend.app.repositories.channels import ChannelRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs

class VideoService:
    """Orchestrates video generation via VideoGenerationService and tracks metadata in MongoDB."""
    
    def __init__(self, db, storage=None, ai_gateway: Optional[AIGateway] = None):
        self.video_repo = VideoRepository(db)
        self.asset_repo = VideoAssetRepository(db)
        self.job_repo = JobRepository(db)
        self.channel_repo = ChannelRepository(db)
        self.storage = storage
        self.video_engine = VideoGenerationService(ai_client=ai_gateway)
        self.ai = ai_gateway
    
    async def create_video_job(self, user_id: str, channel_id: str, request_data: dict) -> dict:
        # 1. Verify channel ownership
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found or access denied")
            
        topic = request_data.get("topic", "Untitled Video")
        title = request_data.get("title") or topic
        
        # 2. Create video document
        video_doc = {
            "user_id": user_id,
            "channel_id": channel_id,
            "title": title,
            "description": request_data.get("description", ""),
            "script_id": request_data.get("script_id"),
            "status": "queued",
            "request_data": request_data,
            "file_path": None,
            "duration": None,
            "width": None,
            "height": None,
            "size_bytes": None,
            "thumbnail_path": None,
            "youtube_video_id": None,
            "published_at": None,
            "tags": request_data.get("tags", [])
        }
        video_id = await self.video_repo.insert_one(video_doc)
        
        # 3. Enqueue background job
        job_payload = {
            "video_id": str(video_id),
            "channel_id": channel_id,
            "request_data": request_data
        }
        job_id = await self.job_repo.enqueue(
            job_type="video_generation",
            user_id=user_id,
            channel_id=channel_id,
            payload=job_payload
        )
        
        return {
            "video_id": str(video_id),
            "job_id": str(job_id),
            "status": "queued"
        }
    
    async def get_video(self, user_id: str, video_id: str) -> Optional[dict]:
        video = await self.video_repo.find_by_id(video_id, user_id=user_id)
        return serialize_doc(video)
        
    async def list_videos(self, user_id: str, channel_id: Optional[str] = None, status: Optional[str] = None) -> List[dict]:
        videos = await self.video_repo.find_by_channel(user_id=user_id, channel_id=channel_id, status=status)
        return serialize_docs(videos)
        
    async def get_video_progress(self, user_id: str, job_id: str) -> Optional[dict]:
        job = await self.job_repo.find_by_id(job_id, user_id=user_id)
        return serialize_doc(job)
    
    async def process_video_job(self, job: dict, progress_callback: Optional[Callable[[PipelineProgress], None]] = None) -> dict:
        """Executed by worker to generate video assets and persist metadata to MongoDB."""
        payload = job.get("payload", {})
        request_data = payload.get("request_data", {})
        video_id = payload.get("video_id")
        user_id = job["user_id"]
        channel_id = job.get("channel_id")
        
        # Mark video status as generating
        await self.video_repo.update_status(video_id, user_id=user_id, status="generating")
        
        # Construct VideoGenerationRequest
        gen_request = VideoGenerationRequest(
            topic=request_data.get("topic", "AI Video"),
            script=request_data.get("script", ""),
            duration=int(request_data.get("duration", 45)),
            aspect_ratio=request_data.get("aspect_ratio", "9:16"),
            voice_name=request_data.get("voice_name", "en-US-AriaNeural"),
            voice_rate=float(request_data.get("voice_rate", 1.0)),
            subtitle_enabled=bool(request_data.get("subtitle_enabled", True)),
            font_size=int(request_data.get("font_size", 60)),
            text_color=request_data.get("text_color", "#FFFFFF"),
            video_source=request_data.get("video_source", "local"),
            output_dir=request_data.get("output_dir", "")
        )
        
        # Run generation pipeline
        result: VideoGenerationResult = await self.video_engine.generate(
            request=gen_request,
            progress_callback=progress_callback
        )
        
        # Persist to permanent storage under media/videos/{channel_id}/{video_id}.mp4
        media_root = getattr(self.storage, "root_dir", "media") if self.storage else "media"
        perm_dir = os.path.join(media_root, "videos", str(channel_id))
        os.makedirs(perm_dir, exist_ok=True)
        perm_file = os.path.join(perm_dir, f"{video_id}.mp4")
        
        import shutil
        if os.path.exists(result.video_path):
            shutil.copy2(result.video_path, perm_file)
            final_file_path = os.path.abspath(perm_file)
        else:
            final_file_path = result.video_path
            
        stream_url = f"/api/videos/{video_id}/stream"
        
        # Update video record with generated metadata
        update_data = {
            "status": "generated",
            "file_path": final_file_path,
            "stream_url": stream_url,
            "duration": result.duration,
            "width": result.width,
            "height": result.height,
            "size_bytes": result.size_bytes
        }
        await self.video_repo.update_one(video_id, update_data, user_id=user_id)
        
        # Create video asset records
        if result.audio_path:
            await self.asset_repo.create_asset({
                "video_id": video_id,
                "user_id": user_id,
                "asset_type": "audio",
                "file_path": result.audio_path,
                "duration": result.duration
            })
        if result.subtitle_path:
            await self.asset_repo.create_asset({
                "video_id": video_id,
                "user_id": user_id,
                "asset_type": "subtitle",
                "file_path": result.subtitle_path,
                "duration": result.duration
            })
            
        result_dict = result.model_dump()
        result_dict["stream_url"] = stream_url
        result_dict["video_id"] = str(video_id)
        result_dict["permanent_path"] = final_file_path
        return result_dict
    
    async def delete_video(self, user_id: str, video_id: str) -> bool:
        return await self.video_repo.delete_one(video_id, user_id=user_id)