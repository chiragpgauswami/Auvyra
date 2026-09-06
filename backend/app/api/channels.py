from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.services.channel_service import ChannelService
from pydantic import BaseModel

router = APIRouter(prefix="/api/channels", tags=["channels"])

class ChannelCreate(BaseModel):
    name: str
    description: str = ""

class ChannelUpdate(BaseModel):
    name: str = None
    description: str = None

class AutopilotToggle(BaseModel):
    enabled: bool

def get_channel_service(db = Depends(get_db)):
    return ChannelService(db)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_channel(data: ChannelCreate, user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    return await service.create_channel(str(user["_id"]), data.model_dump())

@router.get("/")
async def list_channels(user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    return await service.list_channels(str(user["_id"]))

@router.get("/{channel_id}")
async def get_channel(channel_id: str, user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    channel = await service.get_channel(str(user["_id"]), channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel

@router.put("/{channel_id}")
async def update_channel(channel_id: str, data: ChannelUpdate, user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    updated = await service.update_channel(str(user["_id"]), channel_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"status": "success"}

@router.delete("/{channel_id}")
async def delete_channel(channel_id: str, user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    deleted = await service.delete_channel(str(user["_id"]), channel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"status": "success"}

@router.get("/{channel_id}/memory")
async def get_channel_memory(channel_id: str, user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    memory = await service.get_memory(str(user["_id"]), channel_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory

@router.put("/{channel_id}/autopilot")
async def toggle_autopilot(channel_id: str, data: AutopilotToggle, user: dict = Depends(require_auth), service: ChannelService = Depends(get_channel_service)):
    updated = await service.toggle_autopilot(str(user["_id"]), channel_id, data.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"status": "success"}