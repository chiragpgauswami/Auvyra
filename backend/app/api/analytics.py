from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.analytics_service import AnalyticsService
from backend.app.ai.gateway import AIGateway

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

def get_analytics_service(db = Depends(get_db), settings = Depends(get_settings)):
    ai = AIGateway(settings)
    return AnalyticsService(db, ai)

@router.get("/channel/{channel_id}")
async def get_channel_analytics(channel_id: str, period: str = "daily", user: dict = Depends(require_auth), service: AnalyticsService = Depends(get_analytics_service)):
    return await service.get_channel_analytics(str(user["_id"]), channel_id, period)

@router.get("/video/{video_id}")
async def get_video_analytics(video_id: str, user: dict = Depends(require_auth), service: AnalyticsService = Depends(get_analytics_service)):
    return await service.get_video_analytics(str(user["_id"]), video_id)

@router.get("/insights/{channel_id}")
async def get_insights(channel_id: str, user: dict = Depends(require_auth), service: AnalyticsService = Depends(get_analytics_service)):
    return await service.get_insights(str(user["_id"]), channel_id)

@router.post("/insights/{channel_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate_insights(channel_id: str, user: dict = Depends(require_auth), service: AnalyticsService = Depends(get_analytics_service)):
    return await service.generate_insights(str(user["_id"]), channel_id)