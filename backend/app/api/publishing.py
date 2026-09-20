from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.services.publishing_service import PublishingService
from backend.app.youtube.client import YouTubeAPIError
from pydantic import BaseModel

router = APIRouter(prefix="/api/publishing", tags=["publishing"])

class PublishingCreateReq(BaseModel):
    video_id: str
    platform: str = "youtube"
    metadata: dict = {}
    scheduled_at: Optional[datetime] = None

def get_publishing_service(db = Depends(get_db)):
    return PublishingService(db)

@router.post("", status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_publishing_job(
    req: PublishingCreateReq,
    user: dict = Depends(require_auth),
    service: PublishingService = Depends(get_publishing_service)
):
    try:
        job_doc = await service.create_publishing_job(
            user_id=str(user["_id"]),
            video_id=req.video_id,
            platform=req.platform,
            metadata=req.metadata,
            scheduled_at=req.scheduled_at
        )
        job_id = job_doc.get("id") if isinstance(job_doc, dict) else str(job_doc)
        return {"job_id": job_id, "job": job_doc}
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(e)})

@router.get("", include_in_schema=False)
@router.get("/")
async def list_publishing_jobs(
    user: dict = Depends(require_auth),
    service: PublishingService = Depends(get_publishing_service)
):
    return await service.list_publishing_jobs(str(user["_id"]))

@router.get("/calendar/", include_in_schema=False)
@router.get("/calendar")
async def get_publishing_calendar(
    user: dict = Depends(require_auth),
    service: PublishingService = Depends(get_publishing_service)
):
    return await service.get_publishing_calendar(str(user["_id"]))

@router.get("/{job_id}/", include_in_schema=False)
@router.get("/{job_id}")
async def get_publishing_status(
    job_id: str,
    user: dict = Depends(require_auth),
    service: PublishingService = Depends(get_publishing_service)
):
    job = await service.get_publishing_status(str(user["_id"]), job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})
    return job

@router.post("/{job_id}/publish/", include_in_schema=False)
@router.post("/{job_id}/publish")
async def execute_publish(
    job_id: str,
    user: dict = Depends(require_auth),
    service: PublishingService = Depends(get_publishing_service)
):
    try:
        return await service.execute_publish(str(user["_id"]), job_id)
    except YouTubeAPIError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.error_code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(e)})
