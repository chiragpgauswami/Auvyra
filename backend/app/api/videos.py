from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.video_service import VideoService
from backend.app.storage.local import LocalStorageProvider
from backend.app.ai.gateway import AIGateway
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/videos", tags=["videos"])

class VideoGenerateReq(BaseModel):
    channel_id: str
    request_data: dict

def get_video_service(db = Depends(get_db), settings = Depends(get_settings)):
    storage = LocalStorageProvider(settings.MEDIA_ROOT)
    ai = AIGateway(settings)
    return VideoService(db, storage, ai)

@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_video(req: VideoGenerateReq, user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    try:
        return await service.create_video_job(str(user["_id"]), req.channel_id, req.request_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHANNEL_NOT_FOUND", "message": str(e)}
        )

@router.get("/")
async def list_videos(channel_id: Optional[str] = Query(None), status: Optional[str] = Query(None), user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    return await service.list_videos(str(user["_id"]), channel_id, status)

@router.get("/{video_id}")
async def get_video(video_id: str, user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    video = await service.get_video(str(user["_id"]), video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VIDEO_NOT_FOUND", "message": f"Video {video_id} not found or access denied"}
        )
    return video

@router.get("/jobs/{job_id}/progress")
async def get_video_progress(job_id: str, user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    progress = await service.get_video_progress(str(user["_id"]), job_id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found or access denied"}
        )
    return progress

@router.delete("/{video_id}")
async def delete_video(video_id: str, user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    deleted = await service.delete_video(str(user["_id"]), video_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VIDEO_NOT_FOUND", "message": f"Video {video_id} not found or access denied"}
        )
    return {"status": "success"}