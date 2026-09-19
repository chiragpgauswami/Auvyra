from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from bson import ObjectId

from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.autopilot_service import AutopilotService
from backend.app.services.scheduler_service import SchedulerService
from backend.app.repositories.autopilot_events import AutopilotEventsRepository
from backend.app.ai.gateway import AIGateway
from backend.app.utils.serializers import serialize_doc, serialize_docs

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])

class AutopilotToggleReq(BaseModel):
    enabled: bool
    approval_required: bool = True

def get_autopilot_service(db = Depends(get_db), settings = Depends(get_settings)):
    ai = AIGateway(settings)
    return AutopilotService(db, ai)

def get_scheduler_service(db = Depends(get_db)):
    return SchedulerService(db)

def get_events_repo(db = Depends(get_db)):
    return AutopilotEventsRepository(db)

@router.post("/{channel_id}/toggle")
async def toggle_autopilot(
    channel_id: str,
    req: AutopilotToggleReq,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    try:
        channel = await service.channel_repo.find_by_id(channel_id, user_id=str(user["_id"]))
        if not channel:
            raise HTTPException(status_code=404, detail={"code": "CHANNEL_NOT_FOUND", "message": "Channel not found or unauthorized"})

        update_data = {
            "autopilot_enabled": req.enabled,
            "approval_required": req.approval_required
        }
        await service.channel_repo.update_one(channel_id, update_data, user_id=str(user["_id"]))
        channel.update(update_data)
        return serialize_doc(channel)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": str(e)})

@router.get("/{channel_id}/status")
async def get_autopilot_status(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    channel = await service.channel_repo.find_by_id(channel_id, user_id=str(user["_id"]))
    if not channel:
        raise HTTPException(status_code=404, detail={"code": "CHANNEL_NOT_FOUND", "message": "Channel not found or unauthorized"})

    brain = await service.brain_repo.find_by_channel(channel_id, str(user["_id"]))
    upcoming_slots = await service.queue_repo.find_by_channel(channel_id, str(user["_id"]), limit=10)

    return {
        "channel_id": channel_id,
        "name": channel.get("name"),
        "autopilot_enabled": channel.get("autopilot_enabled", False),
        "approval_required": channel.get("approval_required", True),
        "strategy_version": brain.get("strategy_version", 1) if brain else 1,
        "niche": brain.get("niche") if brain else "General",
        "upcoming_slots_count": len(upcoming_slots)
    }

@router.get("/{channel_id}/events")
async def get_channel_events(
    channel_id: str,
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service),
    events_repo: AutopilotEventsRepository = Depends(get_events_repo)
):
    """Retrieve append-only telemetry events for this channel."""
    channel = await service.channel_repo.find_by_id(channel_id, user_id=str(user["_id"]))
    if not channel:
        raise HTTPException(status_code=404, detail={"code": "CHANNEL_NOT_FOUND", "message": "Channel not found or unauthorized"})

    events = await events_repo.find_by_channel(channel_id, str(user["_id"]), limit=limit)
    return serialize_docs(events)

@router.post("/queue/{slot_id}/approve")
async def approve_queue_slot(
    slot_id: str,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    """Approves a video in ready_for_approval state to proceed with upload."""
    try:
        res = await service.approve_queue_item(
            user_id=str(user["_id"]),
            queue_item_id=slot_id,
            worker_id="api_approval"
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "APPROVAL_FAILED", "message": str(e)})

@router.post("/queue/{slot_id}/retry")
async def retry_queue_slot(
    slot_id: str,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    """Resets failed stage and resumes execution from checkpoint."""
    try:
        res = await service.retry_queue_item(
            user_id=str(user["_id"]),
            queue_item_id=slot_id,
            worker_id="api_retry"
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SLOT", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "RETRY_FAILED", "message": str(e)})

@router.delete("/queue/{slot_id}")
async def cancel_queue_slot(
    slot_id: str,
    user: dict = Depends(require_auth),
    service: AutopilotService = Depends(get_autopilot_service)
):
    """Deletes or cancels a pending or failed scheduled slot."""
    oid = ObjectId(slot_id) if ObjectId.is_valid(slot_id) else slot_id
    res = await service.db.autopilot_queue.delete_one({"_id": oid, "user_id": str(user["_id"])})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail={"code": "SLOT_NOT_FOUND", "message": "Slot not found or unauthorized"})
    return {"status": "success", "deleted_slot_id": slot_id}

@router.post("/scheduler/tick")
async def trigger_scheduler_tick(
    user: dict = Depends(require_auth),
    scheduler: SchedulerService = Depends(get_scheduler_service)
):
    """Triggers an immediate scheduler tick (reclaims leases, replenishes bounded queue, dispatches due slots)."""
    res = await scheduler.tick()
    return res
