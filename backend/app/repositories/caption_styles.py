from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from backend.app.repositories.base import BaseRepository
from backend.app.models.caption_style import PRESET_STYLES, CaptionStyleConfig

class CaptionStyleRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db, "caption_style_configs")

    def list_presets(self) -> List[Dict[str, Any]]:
        return PRESET_STYLES

    def get_preset(self, style_id: str) -> Optional[Dict[str, Any]]:
        for p in PRESET_STYLES:
            if p["style_id"] == style_id:
                return dict(p)
        return None

    async def get_channel_style(self, channel_id: str, user_id: str) -> Dict[str, Any]:
        """
        Fetches the active caption style configuration for a channel.
        Falls back to default 'bold' preset if none explicitly saved.
        Strict multi-tenant channel isolation enforced.
        """
        doc = await self.collection.find_one({"channel_id": channel_id, "user_id": user_id})
        if doc:
            doc["id"] = str(doc.pop("_id", ""))
            return doc

        # Fallback to bold preset
        default_preset = self.get_preset("bold") or PRESET_STYLES[0]
        cfg = dict(default_preset["config"])
        cfg["channel_id"] = channel_id
        cfg["user_id"] = user_id
        cfg["updated_at"] = datetime.now(timezone.utc)
        return cfg

    async def save_channel_style(self, channel_id: str, user_id: str, config_data: dict) -> Dict[str, Any]:
        """
        Persists updated caption style for a channel.
        Enforces user ownership and increments configuration version.
        """
        now = datetime.now(timezone.utc)
        clean_data = dict(config_data)
        clean_data.pop("_id", None)
        clean_data.pop("id", None)
        clean_data["channel_id"] = channel_id
        clean_data["user_id"] = user_id
        clean_data["updated_at"] = now
        
        # Increment version
        existing = await self.collection.find_one({"channel_id": channel_id, "user_id": user_id})
        current_version = existing.get("version", 0) if existing else 0
        clean_data["version"] = current_version + 1

        await self.collection.update_one(
            {"channel_id": channel_id, "user_id": user_id},
            {"$set": clean_data},
            upsert=True
        )

        return await self.get_channel_style(channel_id, user_id)

