from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.video_service import VideoService
from backend.app.storage.local import LocalStorageProvider
from backend.app.ai.gateway import AIGateway
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(prefix="/api/videos", tags=["videos"])

class VideoGenerateReq(BaseModel):
    channel_id: Optional[str] = None
    request_data: Optional[dict] = None
    topic: Optional[str] = None
    script: Optional[str] = None
    aspect_ratio: Optional[str] = "9:16"
    voice: Optional[str] = None
    duration: Optional[int] = 45

def get_video_service(db = Depends(get_db), settings = Depends(get_settings)):
    storage = LocalStorageProvider(settings.MEDIA_ROOT)
    ai = AIGateway(settings)
    return VideoService(db, storage, ai)

@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_video(req: VideoGenerateReq, user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    user_id = str(user["_id"])
    target_channel_id = req.channel_id
    if not target_channel_id:
        from backend.app.repositories.channels import ChannelRepository
        ch_repo = ChannelRepository(service.video_repo.db)
        user_channels = await ch_repo.find_by_user(user_id)
        if user_channels:
            target_channel_id = str(user_channels[0]["_id"])
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "CHANNEL_REQUIRED", "message": "Please create or connect a channel before generating videos."}
            )

    req_data = req.request_data or {}
    if req.topic and "topic" not in req_data:
        req_data["topic"] = req.topic
    if req.script and "script" not in req_data:
        req_data["script"] = req.script
    if req.aspect_ratio and "aspect_ratio" not in req_data:
        req_data["aspect_ratio"] = req.aspect_ratio
    if req.voice and "voice" not in req_data:
        req_data["voice"] = req.voice
    if req.duration and "duration" not in req_data:
        req_data["duration"] = req.duration

    try:
        return await service.create_video_job(user_id, target_channel_id, req_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHANNEL_NOT_FOUND", "message": str(e)}
        )

@router.get("", include_in_schema=False)
@router.get("/")
async def list_videos(channel_id: Optional[str] = Query(None), status: Optional[str] = Query(None), user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    return await service.list_videos(str(user["_id"]), channel_id, status)

@router.get("/latest")
async def get_latest_video(channel_id: Optional[str] = Query(None), user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    video = await service.get_latest_video(str(user["_id"]), channel_id)
    if not video:
        return {"video": None}
    return {"video": video}

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

import os
import tempfile
from fastapi import Request
from fastapi.responses import StreamingResponse, FileResponse
from backend.app.auth.dependencies import get_auth_service
from backend.app.auth.service import AuthService

def _validate_safe_video_path(file_path: str, allowed_dirs: list[str]) -> str:
    """Ensure file_path is strictly within allowed directories and free of traversal attacks."""
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FILE_NOT_FOUND", "message": "Video media file path not specified"}
        )
    if ".." in file_path:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PATH_TRAVERSAL_DETECTED", "message": "Path traversal sequence not allowed"}
        )
    real_path = os.path.realpath(file_path)
    allowed = False
    for d in allowed_dirs:
        real_d = os.path.realpath(d)
        if real_path == real_d or real_path.startswith(real_d + os.sep):
            allowed = True
            break
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PATH_TRAVERSAL_DETECTED", "message": "Access to requested file path is forbidden"}
        )
    return real_path

async def _resolve_and_authorize_video(
    video_id: str,
    request: Request,
    token: Optional[str],
    service: VideoService,
    auth_service: AuthService
) -> tuple[dict, str]:
    video = await service.video_repo.find_by_id(video_id)
    if not video:
        job = await service.job_repo.find_by_id(video_id)
        if job and job.get("result", {}).get("video_id"):
            video = await service.video_repo.find_by_id(job["result"]["video_id"])
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VIDEO_NOT_FOUND", "message": f"Video {video_id} not found"}
        )

    # Authorization verification
    raw_token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        raw_token = auth_header.split(" ", 1)[1].strip()
    elif token:
        raw_token = token

    caller_user = None
    if raw_token:
        try:
            caller_user = await auth_service.get_current_user(raw_token)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": "Invalid authentication token"}
            )

    video_owner_id = video.get("user_id")
    if video_owner_id:
        if not caller_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "UNAUTHORIZED", "message": "Authentication required to access this video"}
            )
        if str(video_owner_id) != str(caller_user["_id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You do not have permission to access this video"}
            )

    file_path = video.get("file_path")
    settings = get_settings()
    allowed_roots = [
        str(service.storage.root_dir),
        settings.MEDIA_ROOT,
        os.path.abspath("media"),
        tempfile.gettempdir()
    ]
    safe_path = _validate_safe_video_path(file_path, allowed_roots)

    if not os.path.exists(safe_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FILE_NOT_FOUND", "message": "Video media file not found on disk"}
        )

    return video, safe_path

@router.get("/{video_id}/stream")
async def stream_video(
    video_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    service: VideoService = Depends(get_video_service),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Stream video with full HTTP 206 Partial Content (Range request) support for browser playback."""
    video, file_path = await _resolve_and_authorize_video(video_id, request, token, service, auth_service)

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range")
    
    if range_header and range_header.startswith("bytes="):
        # Parse range header e.g. "bytes=0-1048575"
        bytes_spec = range_header.replace("bytes=", "").strip()
        parts = bytes_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        
        # Clamp ranges
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = end - start + 1
        
        def iter_video():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = content_length
                chunk_size = 128 * 1024
                while bytes_left > 0:
                    read_len = min(chunk_size, bytes_left)
                    chunk = f.read(read_len)
                    if not chunk:
                        break
                    bytes_left -= len(chunk)
                    yield chunk
                    
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": "video/mp4",
            "Cache-Control": "public, max-age=3600"
        }
        return StreamingResponse(iter_video(), status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers)
    else:
        return FileResponse(file_path, media_type="video/mp4", filename=f"{video_id}.mp4")

@router.get("/{video_id}/download")
async def download_video(
    video_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    service: VideoService = Depends(get_video_service),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Download the raw MP4 video file as an attachment."""
    video, file_path = await _resolve_and_authorize_video(video_id, request, token, service, auth_service)

    clean_title = "".join(c for c in video.get("title", "video") if c.isalnum() or c in (" ", "_", "-")).strip()
    return FileResponse(file_path, media_type="video/mp4", filename=f"{clean_title or 'video'}.mp4")

@router.get("/{video_id}/thumbnail")
async def get_video_thumbnail(
    video_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    service: VideoService = Depends(get_video_service),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Retrieve the generated video thumbnail image with resilient path resolution and on-demand self-healing."""
    video = await service.video_repo.find_by_id(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VIDEO_NOT_FOUND", "message": f"Video {video_id} not found"}
        )

    # Validate caller user if auth token provided
    auth_header = request.headers.get("Authorization")
    token_str = auth_header.split(" ")[1] if (auth_header and auth_header.startswith("Bearer ")) else token
    if token_str:
        try:
            caller_user = await auth_service.get_current_user(token_str)
            video_owner_id = video.get("user_id")
            if video_owner_id and caller_user and str(video_owner_id) != str(caller_user["_id"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"code": "FORBIDDEN", "message": "Access denied"}
                )
        except HTTPException:
            raise
        except Exception:
            pass  # Allow graceful rendering of public video thumbnail

    settings = get_settings()
    thumb_path = video.get("thumbnail_path")
    resolved_thumb: Optional[str] = None

    if thumb_path:
        candidates = [thumb_path]
        if not os.path.isabs(thumb_path):
            candidates.extend([
                os.path.abspath(thumb_path),
                os.path.join(settings.MEDIA_ROOT, thumb_path),
                os.path.join(os.path.abspath("media"), thumb_path),
            ])
        for cand in candidates:
            if os.path.exists(cand) and os.path.isfile(cand):
                resolved_thumb = os.path.abspath(cand)
                break

    # If thumbnail missing from disk but video MP4 exists, extract frame on-demand (self-healing)
    if not resolved_thumb:
        file_path = video.get("file_path")
        if file_path and os.path.exists(file_path):
            try:
                from backend.app.services.thumbnail_service import ThumbnailService
                channel_id = str(video.get("channel_id", "default"))
                thumb_dir = os.path.join(settings.MEDIA_ROOT, "thumbnails", channel_id)
                os.makedirs(thumb_dir, exist_ok=True)
                new_thumb_file = os.path.join(thumb_dir, f"{video_id}.jpg")
                thumb_service = ThumbnailService(output_dir=thumb_dir)
                thumb_service.extract_best_frame(file_path, new_thumb_file)
                if os.path.exists(new_thumb_file):
                    resolved_thumb = os.path.abspath(new_thumb_file)
                    await service.video_repo.update_one(
                        video_id,
                        {
                            "thumbnail_path": resolved_thumb,
                            "thumbnail_url": f"/api/videos/{video_id}/thumbnail"
                        },
                        user_id=video.get("user_id")
                    )
            except Exception as ex:
                logger.warning(f"On-demand thumbnail extraction failed for video {video_id}: {ex}")

    if not resolved_thumb or not os.path.exists(resolved_thumb):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "THUMBNAIL_NOT_FOUND", "message": "Thumbnail image not found"}
        )

    return FileResponse(resolved_thumb, media_type="image/jpeg", filename=f"{video_id}.jpg")

@router.delete("/{video_id}")
async def delete_video(video_id: str, user: dict = Depends(require_auth), service: VideoService = Depends(get_video_service)):
    deleted = await service.delete_video(str(user["_id"]), video_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "VIDEO_NOT_FOUND", "message": f"Video {video_id} not found or access denied"}
        )
    return {"status": "success"}