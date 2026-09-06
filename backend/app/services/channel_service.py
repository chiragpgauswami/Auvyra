from typing import Dict, List, Optional
from loguru import logger
from backend.app.repositories.channels import ChannelRepository, ChannelMemoryRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs

class ChannelService:
    def __init__(self, db):
        self.channel_repo = ChannelRepository(db)
        self.memory_repo = ChannelMemoryRepository(db)
    
    async def create_channel(self, user_id: str, data: dict) -> dict:
        data["user_id"] = user_id
        channel_id = await self.channel_repo.insert_one(data)
        data["id"] = channel_id
        return serialize_doc(data)
        
    async def list_channels(self, user_id: str, skip: int = 0, limit: int = 50) -> List[dict]:
        channels = await self.channel_repo.find_by_user(user_id=user_id, skip=skip, limit=limit)
        return serialize_docs(channels)
        
    async def get_channel(self, user_id: str, channel_id: str) -> Optional[dict]:
        channel = await self.channel_repo.find_by_id(channel_id, user_id=user_id)
        return serialize_doc(channel)
        
    async def update_channel(self, user_id: str, channel_id: str, data: dict) -> bool:
        return await self.channel_repo.update_one(channel_id, data, user_id=user_id)
        
    async def delete_channel(self, user_id: str, channel_id: str) -> bool:
        return await self.channel_repo.delete_one(channel_id, user_id=user_id)
        
    async def get_memory(self, user_id: str, channel_id: str) -> Optional[dict]:
        channel = await self.get_channel(user_id, channel_id)
        if not channel:
            return None
        memory = await self.memory_repo.get_memory(channel_id)
        return serialize_doc(memory)
        
    async def toggle_autopilot(self, user_id: str, channel_id: str, enabled: bool) -> bool:
        return await self.channel_repo.update_one(channel_id, {"autopilot_enabled": enabled}, user_id=user_id)