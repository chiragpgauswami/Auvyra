from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.repositories.caption_styles import CaptionStyleRepository
from backend.app.repositories.channels import ChannelRepository
from backend.app.models.caption_style import CaptionStyleConfig

router = APIRouter(prefix="/api/caption-styles", tags=["caption-styles"])

@router.get("/presets", response_model=List[Dict[str, Any]])
async def list_caption_presets(user: dict = Depends(require_auth), db=Depends(get_db)):
    """Returns curated 6 high-retention caption style presets."""
    repo = CaptionStyleRepository(db)
    return repo.list_presets()

@router.get("/channels/{channel_id}", response_model=Dict[str, Any])
async def get_channel_caption_style(channel_id: str, user: dict = Depends(require_auth), db=Depends(get_db)):
    """Fetches the active caption style configuration for a channel."""
    user_id = str(user["_id"])
    chan_repo = ChannelRepository(db)
    channel = await chan_repo.find_by_id(channel_id, user_id=user_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or unauthorized")

    repo = CaptionStyleRepository(db)
    return await repo.get_channel_style(channel_id, user_id)

@router.put("/channels/{channel_id}", response_model=Dict[str, Any])
async def update_channel_caption_style(channel_id: str, config: CaptionStyleConfig, user: dict = Depends(require_auth), db=Depends(get_db)):
    """Updates the caption style configuration for a channel. Preserves existing queue item snapshots."""
    user_id = str(user["_id"])
    chan_repo = ChannelRepository(db)
    channel = await chan_repo.find_by_id(channel_id, user_id=user_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or unauthorized")

    repo = CaptionStyleRepository(db)
    saved = await repo.save_channel_style(channel_id, user_id, config.model_dump())
    return saved

