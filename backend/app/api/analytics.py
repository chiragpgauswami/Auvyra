from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.analytics_service import AnalyticsService
from backend.app.youtube.client import YouTubeAPIError
from backend.app.ai.gateway import AIGateway
from pydantic import BaseModel

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

class AnalyticsSyncReq(BaseModel):
    start_date: Optional[str] = None

def get_analytics_service(db = Depends(get_db), settings = Depends(get_settings)):
    ai = AIGateway(settings)
    return AnalyticsService(db, ai)

@router.get("/channel/{channel_id}")
async def get_channel_analytics(
    channel_id: str,
    period: str = "daily",
    user: dict = Depends(require_auth),
    service: AnalyticsService = Depends(get_analytics_service)
):
    return await service.get_channel_analytics(str(user["_id"]), channel_id, period)

@router.post("/channel/{channel_id}/sync")
async def sync_channel_analytics(
    channel_id: str,
    req: AnalyticsSyncReq = AnalyticsSyncReq(),
    user: dict = Depends(require_auth),
    service: AnalyticsService = Depends(get_analytics_service)
):
    try:
        return await service.sync_channel_analytics(str(user["_id"]), channel_id, req.start_date)
    except YouTubeAPIError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.error_code, "message": e.message})
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(e)})

@router.get("/video/{video_id}")
async def get_video_analytics(
    video_id: str,
    user: dict = Depends(require_auth),
    service: AnalyticsService = Depends(get_analytics_service)
):
    return await service.get_video_analytics(str(user["_id"]), video_id)

@router.get("/insights/{channel_id}")
async def get_insights(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: AnalyticsService = Depends(get_analytics_service)
):
    return await service.get_insights(str(user["_id"]), channel_id)

@router.post("/insights/{channel_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate_insights(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: AnalyticsService = Depends(get_analytics_service)
):
    return await service.generate_insights(str(user["_id"]), channel_id)
