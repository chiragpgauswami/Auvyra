from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.services.publishing_service import PublishingService
from pydantic import BaseModel

router = APIRouter(prefix="/api/publishing", tags=["publishing"])

class PublishingCreateReq(BaseModel):
    video_id: str
    platform: str = "youtube"
    metadata: dict = {}

def get_publishing_service(db = Depends(get_db)):
    return PublishingService(db)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_publishing_job(req: PublishingCreateReq, user: dict = Depends(require_auth), service: PublishingService = Depends(get_publishing_service)):
    try:
        job_id = await service.create_publishing_job(str(user["_id"]), req.video_id, req.platform, req.metadata)
        return {"job_id": job_id}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.get("/")
async def list_publishing_jobs(user: dict = Depends(require_auth), service: PublishingService = Depends(get_publishing_service)):
    return await service.list_publishing_jobs(str(user["_id"]))

@router.get("/{job_id}")
async def get_publishing_status(job_id: str, user: dict = Depends(require_auth), service: PublishingService = Depends(get_publishing_service)):
    job = await service.get_publishing_status(str(user["_id"]), job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job