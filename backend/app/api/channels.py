from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Dict, Any, Optional
from bson import ObjectId
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

from backend.app.config import get_settings
from backend.app.youtube.scopes import REQUIRED_YOUTUBE_SCOPES, verify_granted_scopes
from backend.app.youtube.client import YouTubeClient, YouTubeAPIError

def get_channel_service(db = Depends(get_db)):
    return ChannelService(db)

@router.get("/youtube/status")
async def get_youtube_connection_status(
    user: dict = Depends(require_auth),
    db = Depends(get_db)
):
    """Retrieve Google OAuth and YouTube integration status for the authenticated user."""
    user_id = str(user["_id"])
    oauth = await db.oauth_accounts.find_one({"user_id": user_id, "provider": "google"})
    if not oauth:
        return {
            "connected": False,
            "status": "not_connected",
            "message": "YouTube account is not connected. Click Connect YouTube to link your channel."
        }

    granted_scopes = oauth.get("granted_scopes", [])
    audit = verify_granted_scopes(granted_scopes)
    
    # Find linked channel
    channel = await db.channels.find_one({"user_id": user_id, "youtube_channel_id": {"$exists": True, "$ne": None}})
    
    if audit["needs_reauthorization"]:
        return {
            "connected": True,
            "status": "reauthorization_required",
            "granted_scopes": granted_scopes,
            "missing_scopes": audit["missing_scopes"],
            "needs_reauthorization": True,
            "channel_id": str(channel["_id"]) if channel else None,
            "youtube_channel_id": channel.get("youtube_channel_id") if channel else None,
            "message": "YouTube permissions are incomplete. Please reconnect your YouTube account."
        }

    return {
        "connected": True,
        "status": "connected",
        "granted_scopes": granted_scopes,
        "missing_scopes": [],
        "needs_reauthorization": False,
        "channel": {
            "id": str(channel["_id"]),
            "name": channel.get("name"),
            "handle": channel.get("handle"),
            "youtube_channel_id": channel.get("youtube_channel_id"),
            "thumbnail_url": channel.get("thumbnail_url"),
            "subscriber_count": channel.get("subscriber_count", 0),
            "video_count": channel.get("video_count", 0),
            "view_count": channel.get("view_count", 0),
            "status": channel.get("status", "connected")
        } if channel else None,
        "message": "YouTube account connected and verified."
    }

@router.post("/youtube/sync")
async def sync_youtube_channel(
    account_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    user: dict = Depends(require_auth),
    db = Depends(get_db)
):
    """Trigger live YouTube API lookup to refresh channel details from YouTube Data API v3."""
    user_id = str(user["_id"])
    
    oauth = None
    if account_id:
        try:
            oauth = await db.oauth_accounts.find_one({
                "_id": ObjectId(account_id),
                "user_id": user_id,
                "status": {"$ne": "disconnected"}
            })
        except Exception:
            oauth = None
    elif channel_id:
        try:
            target_ch = await db.channels.find_one({"_id": ObjectId(channel_id), "user_id": user_id})
            if target_ch and target_ch.get("oauth_account_id"):
                oauth = await db.oauth_accounts.find_one({
                    "_id": ObjectId(target_ch["oauth_account_id"]),
                    "user_id": user_id,
                    "status": {"$ne": "disconnected"}
                })
        except Exception:
            oauth = None

    if not oauth:
        oauth = await db.oauth_accounts.find_one({
            "user_id": user_id,
            "provider": "google",
            "status": {"$ne": "disconnected"}
        })

    if not oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NOT_CONNECTED", "message": "Google OAuth is not connected. Please connect YouTube first."}
        )

    granted_scopes = oauth.get("granted_scopes", [])
    has_read = (
        "https://www.googleapis.com/auth/youtube.readonly" in granted_scopes
        or "https://www.googleapis.com/auth/youtube" in granted_scopes
    )
    if not has_read:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "YOUTUBE_INSUFFICIENT_SCOPES",
                "message": "Your YouTube permissions are incomplete (missing https://www.googleapis.com/auth/youtube.readonly). Please reconnect YouTube."
            }
        )

    from backend.app.youtube.client import get_youtube_client_for_channel, get_youtube_client_for_user
    try:
        if channel_id:
            yt_client = await get_youtube_client_for_channel(channel_id, user_id, db)
        else:
            yt_client = await get_youtube_client_for_user(user_id, db)
        channels_info = await yt_client.list_my_channels()
    except YouTubeAPIError as e:
        if e.error_code == "NO_CHANNEL":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NO_CHANNEL", "message": "No YouTube channel was found for this Google account."}
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": e.error_code, "message": e.message}
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    synced_docs = []

    for ch_info in channels_info:
        yt_id = ch_info["youtube_channel_id"]
        existing = await db.channels.find_one({"youtube_channel_id": yt_id})
        update_payload = {
            "user_id": user_id,
            "oauth_account_id": str(oauth["_id"]),
            "google_account_email": oauth.get("email"),
            "name": ch_info["name"],
            "description": ch_info.get("description", ""),
            "handle": ch_info.get("handle") or (existing.get("handle") if existing else None),
            "thumbnail_url": ch_info.get("thumbnail_url") or (existing.get("thumbnail_url") if existing else None),
            "subscriber_count": ch_info.get("subscriber_count", existing.get("subscriber_count", 0) if existing else 0),
            "video_count": ch_info.get("video_count", existing.get("video_count", 0) if existing else 0),
            "view_count": ch_info.get("view_count", existing.get("view_count", 0) if existing else 0),
            "status": "connected",
            "last_synced_at": now,
            "updated_at": now
        }
        if not existing:
            update_payload["youtube_channel_id"] = yt_id
            update_payload["autopilot_enabled"] = False
            update_payload["approval_required"] = True
            update_payload["created_at"] = now
            res = await db.channels.insert_one(update_payload)
            ch_doc = await db.channels.find_one({"_id": res.inserted_id})
        else:
            await db.channels.update_one({"_id": existing["_id"]}, {"$set": update_payload})
            ch_doc = await db.channels.find_one({"_id": existing["_id"]})
        synced_docs.append(ch_doc)

    from backend.app.utils.serializers import serialize_docs, serialize_doc
    if len(synced_docs) == 1:
        return serialize_doc(synced_docs[0])
    return {"channels": serialize_docs(synced_docs)}

@router.delete("/youtube/disconnect")
async def disconnect_youtube_channel(
    account_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    user: dict = Depends(require_auth),
    db = Depends(get_db)
):
    """Safely disconnect YouTube channel without deleting historical data."""
    user_id = str(user["_id"])
    now = datetime.now(timezone.utc)

    if channel_id:
        await db.channels.update_one(
            {"_id": ObjectId(channel_id), "user_id": user_id},
            {"$set": {"status": "disconnected", "autopilot_enabled": False, "updated_at": now}}
        )
        return {"success": True, "message": f"Channel {channel_id} disconnected successfully."}

    if account_id:
        await db.oauth_accounts.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {"$set": {"status": "disconnected", "updated_at": now}}
        )
        await db.channels.update_many(
            {"oauth_account_id": account_id, "user_id": user_id},
            {"$set": {"status": "disconnected", "autopilot_enabled": False, "updated_at": now}}
        )
        return {"success": True, "message": f"OAuth account {account_id} and associated channels disconnected."}

    # Disconnect all active Google accounts
    await db.oauth_accounts.update_many(
        {"user_id": user_id, "provider": "google"},
        {"$set": {"status": "disconnected", "updated_at": now}}
    )
    await db.channels.update_many(
        {"user_id": user_id, "youtube_channel_id": {"$exists": True, "$ne": None}},
        {"$set": {"status": "disconnected", "autopilot_enabled": False, "updated_at": now}}
    )
    return {
        "success": True,
        "message": "All connected YouTube channels safely disconnected. Historical data preserved."
    }

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

from backend.app.models.brain import ChannelOnboardingRequest

@router.post("/{channel_id}/onboard")
async def onboard_channel(
    channel_id: str,
    data: ChannelOnboardingRequest,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Execute AI strategic onboarding for a channel, establishing its Channel Brain."""
    try:
        return await service.onboard_channel(str(user["_id"]), channel_id, data.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Onboarding failed: {str(e)}")

@router.get("/{channel_id}/brain")
async def get_channel_brain(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Fetch isolated Channel Brain strategy and learned rules."""
    brain = await service.get_brain(str(user["_id"]), channel_id)
    if not brain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel Brain not found. Please complete channel onboarding.")
    return brain

@router.post("/{channel_id}/brain/rebuild")
async def rebuild_channel_brain(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Rebuild channel brain strategy based on current niche and past learnings."""
    try:
        return await service.rebuild_brain(str(user["_id"]), channel_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Brain rebuild failed: {str(e)}")


from backend.app.models.channel import AutopilotConfig

@router.get("/{channel_id}/autopilot/niches")
async def get_niche_recommendations(
    channel_id: str,
    refresh: bool = False,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Get context-aware dynamic niche recommendations with honest source tagging and confidence."""
    try:
        return await service.get_niche_recommendations(str(user["_id"]), channel_id, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate niche recommendations: {str(e)}")

@router.post("/{channel_id}/autopilot/configure")
async def configure_autopilot(
    channel_id: str,
    data: AutopilotConfig,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Validate 8-step wizard configuration, update Channel Brain, and bootstrap persistent queue."""
    try:
        return await service.configure_autopilot(str(user["_id"]), channel_id, data.model_dump())
    except ValueError as e:
        err_msg = str(e)
        if "not found or unauthorized" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Configuration failed: {str(e)}")

@router.get("/{channel_id}/autopilot/config")
async def get_autopilot_config(
    channel_id: str,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Fetch current autopilot configuration, operational mode, and upcoming queue summary."""
    try:
        return await service.get_autopilot_config(str(user["_id"]), channel_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch config: {str(e)}")

@router.get("/{channel_id}/autopilot/queue")
async def get_autopilot_queue(
    channel_id: str,
    queue_status: Optional[str] = Query(None, alias="status"),
    limit: int = 50,
    user: dict = Depends(require_auth),
    service: ChannelService = Depends(get_channel_service)
):
    """Fetch persistent scheduled queue items for this channel."""
    try:
        return await service.get_autopilot_queue(str(user["_id"]), channel_id, status=queue_status, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch queue: {str(e)}")