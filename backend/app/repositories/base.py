from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

def safe_object_id(id_val: Any) -> Any:
    if isinstance(id_val, ObjectId):
        return id_val
    if isinstance(id_val, str) and ObjectId.is_valid(id_val):
        return ObjectId(id_val)
    return id_val

class BaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection = db[collection_name]
    
    async def find_by_id(self, id: str, user_id: Optional[str] = None) -> Optional[dict]:
        target_id = safe_object_id(id)
        query: Dict[str, Any] = {"_id": target_id}
        if user_id:
            query["user_id"] = user_id
        return await self.collection.find_one(query)
    
    async def find_many(self, filter: dict, skip: int = 0, limit: int = 50, sort: list | None = None) -> list[dict]:
        cursor = self.collection.find(filter).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return await cursor.to_list(length=limit)
    
    async def count(self, filter: dict) -> int:
        return await self.collection.count_documents(filter)
    
    async def insert_one(self, document: dict) -> str:
        now = datetime.now(timezone.utc)
        document.setdefault("created_at", now)
        document.setdefault("updated_at", now)
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return str(result.inserted_id)
    
    async def update_one(self, id: str, update: dict, user_id: Optional[str] = None) -> bool:
        target_id = safe_object_id(id)
        query: Dict[str, Any] = {"_id": target_id}
        if user_id:
            query["user_id"] = user_id
            
        update["updated_at"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            query,
            {"$set": update}
        )
        return result.modified_count > 0
    
    async def delete_one(self, id: str, user_id: Optional[str] = None) -> bool:
        target_id = safe_object_id(id)
        query: Dict[str, Any] = {"_id": target_id}
        if user_id:
            query["user_id"] = user_id
            
        result = await self.collection.delete_one(query)
        return result.deleted_count > 0
