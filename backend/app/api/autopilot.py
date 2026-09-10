from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from pydantic import BaseModel
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.autopilot_service import AutopilotService
from backend.app.ai.gateway import AIGateway

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])

class AutopilotToggleReq(BaseModel):
    enabled: bool
    approval_required: bool = True

def get_autopilot_service(db = Depends(get_db), settings = Depends(get_settings)):
    ai = AIGateway(settings)
    return AutopilotService(db, ai)

@router.post("/{channel_id}/toggle")
async def toggle_autopilot(
    channel_id: str,
    req: AutopilotToggleReq,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    try:
        return await service.toggle_autopilot(
            user_id=str(user["_id"]),
            channel_id=channel_id,
            enabled=req.enabled,
            approval_required=req.approval_required
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(e)})

@router.post("/{channel_id}/trigger")
async def trigger_autopilot_cycle(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    try:
        return await service.run_autopilot_cycle(
            user_id=str(user["_id"]),
            channel_id=channel_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(e)})
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail={"code": "AUTOPILOT_ERROR", "message": str(e)})

@router.get("/{channel_id}/status")
async def get_autopilot_status(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    channel = await service.channel_repo.find_by_id(channel_id, user_id=str(user["_id"]))
    if not channel:
        raise HTTPException(status_code=404, detail={"code": "CHANNEL_NOT_FOUND", "message": "Channel not found"})

    brain = await service.brain_repo.find_by_channel(channel_id, str(user["_id"]))
    return {
        "channel_id": channel_id,
        "name": channel.get("name"),
        "autopilot_enabled": channel.get("autopilot_enabled", False),
        "approval_required": channel.get("approval_required", True),
        "strategy_version": brain.get("strategy_version", 1) if brain else 1,
        "niche": brain.get("niche") if brain else "General"
    }
