from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from datetime import datetime, timezone
from bson import ObjectId

class ChannelRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "channels")

    async def find_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
        return await self.find_many({"user_id": user_id}, skip=skip, limit=limit)

    async def find_by_youtube_id(self, youtube_channel_id: str) -> dict | None:
        return await self.collection.find_one({"youtube_channel_id": youtube_channel_id})

    async def find_by_oauth_account(self, oauth_account_id: str, user_id: str | None = None) -> list[dict]:
        query = {"oauth_account_id": oauth_account_id}
        if user_id:
            query["user_id"] = user_id
        cursor = self.collection.find(query)
        return await cursor.to_list(length=100)

    async def disconnect_channels_for_oauth_account(self, oauth_account_id: str, user_id: str) -> int:
        """Mark channels associated with this OAuth account as disconnected and pause autopilot, preserving historical data."""
        result = await self.collection.update_many(
            {"oauth_account_id": oauth_account_id, "user_id": user_id},
            {
                "$set": {
                    "status": "disconnected",
                    "autopilot_enabled": False,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        return result.modified_count


class ChannelMemoryRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "channel_memory")

    async def get_memory(self, channel_id: str) -> dict | None:
        return await self.collection.find_one({"channel_id": channel_id})

    async def update_memory(self, channel_id: str, memory_data: dict) -> bool:
        memory_data["last_updated"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"channel_id": channel_id},
            {"$set": memory_data},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def add_insight(self, channel_id: str, insight: dict) -> bool:
        # Insight must include source, confidence, supporting_metrics, created_at
        insight["created_at"] = insight.get("created_at", datetime.now(timezone.utc))
        result = await self.collection.update_one(
            {"channel_id": channel_id},
            {
                "$push": {"strategy_insights": insight},
                "$set": {"last_updated": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None


class AutopilotQueueRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "autopilot_queue")

    async def find_by_channel(self, channel_id: str, user_id: str, status: str | None = None, limit: int = 50) -> list[dict]:
        query = {"channel_id": channel_id, "user_id": user_id}
        if status:
            query["status"] = status
        cursor = self.collection.find(query).sort("scheduled_at", 1).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_slot(self, channel_id: str, scheduled_at: datetime) -> dict | None:
        return await self.collection.find_one({"channel_id": channel_id, "scheduled_at": scheduled_at})

    async def create_slot(self, slot_data: dict) -> str:
        return await self.insert_one(slot_data)

    async def claim_due_slot(self, worker_id: str, now_utc: datetime, lease_duration_seconds: int = 300) -> dict | None:
        """Atomically claim the next due pending slot using find_one_and_update."""
        from datetime import timedelta
        lease_expires = now_utc + timedelta(seconds=lease_duration_seconds)
        doc = await self.collection.find_one_and_update(
            {"status": "pending", "scheduled_at": {"$lte": now_utc}},
            {
                "$set": {
                    "status": "in_production",
                    "current_stage": "channel_sync",
                    "claimed_at": now_utc,
                    "claimed_by": worker_id,
                    "heartbeat_at": now_utc,
                    "lease_expires_at": lease_expires,
                    "updated_at": now_utc
                },
                "$inc": {"attempts": 1}
            },
            return_document=True
        )
        return doc

    async def heartbeat(self, slot_id: str, worker_id: str, extend_seconds: int = 300) -> bool:
        """Extend lease during long-running stage operations."""
        from datetime import timedelta
        now_utc = datetime.now(timezone.utc)
        oid = ObjectId(slot_id) if ObjectId.is_valid(slot_id) else slot_id
        res = await self.collection.update_one(
            {"_id": oid, "claimed_by": worker_id},
            {
                "$set": {
                    "heartbeat_at": now_utc,
                    "lease_expires_at": now_utc + timedelta(seconds=extend_seconds),
                    "updated_at": now_utc
                }
            }
        )
        return res.modified_count > 0

    async def checkpoint_stage(
        self,
        slot_id: str,
        stage: str,
        status: str,
        progress: int = 0,
        artifact_refs: dict = None,
        error: dict = None,
        metadata: dict = None,
        queue_status: str | None = None
    ) -> bool:
        """Persist durable checkpoint for a pipeline stage."""
        now_utc = datetime.now(timezone.utc)
        oid = ObjectId(slot_id) if ObjectId.is_valid(slot_id) else slot_id
        
        stage_record = {
            "status": status,
            "progress": progress,
            "updated_at": now_utc,
            "artifact_refs": artifact_refs or {},
            "error": error,
            "metadata": metadata or {}
        }
        if status == "completed":
            stage_record["completed_at"] = now_utc

        update_fields = {
            f"stages.{stage}": stage_record,
            "current_stage": stage,
            "progress": progress,
            "updated_at": now_utc
        }
        if queue_status:
            update_fields["status"] = queue_status
        if artifact_refs:
            for k, v in artifact_refs.items():
                update_fields[f"artifacts.{k}"] = v

        res = await self.collection.update_one(
            {"_id": oid},
            {"$set": update_fields}
        )
        return res.modified_count > 0

    async def mark_slot_failed(self, slot_id: str, error_info: dict, retryable: bool = False, max_attempts: int = 3) -> bool:
        """Mark slot failed or retrying with machine-readable failure reason."""
        now_utc = datetime.now(timezone.utc)
        oid = ObjectId(slot_id) if ObjectId.is_valid(slot_id) else slot_id
        slot = await self.collection.find_one({"_id": oid})
        attempts = slot.get("attempts", 1) if slot else 1
        
        new_status = "retrying" if (retryable and attempts < max_attempts) else "failed"
        update_fields = {
            "status": new_status,
            "last_error": error_info,
            "failure_reason": error_info.get("message") or error_info.get("code", "UNKNOWN_ERROR"),
            "claimed_by": None,
            "lease_expires_at": None,
            "updated_at": now_utc
        }
        res = await self.collection.update_one({"_id": oid}, {"$set": update_fields})
        return res.modified_count > 0

    async def mark_slot_published(self, slot_id: str, video_id: str, youtube_url: str = None) -> bool:
        """Mark slot successfully published."""
        now_utc = datetime.now(timezone.utc)
        oid = ObjectId(slot_id) if ObjectId.is_valid(slot_id) else slot_id
        res = await self.collection.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": "published",
                    "video_id": video_id,
                    "youtube_url": youtube_url,
                    "published_at": now_utc,
                    "progress": 100,
                    "claimed_by": None,
                    "lease_expires_at": None,
                    "updated_at": now_utc
                }
            }
        )
        return res.modified_count > 0

    async def reclaim_expired_leases(self, now_utc: datetime) -> int:
        """Find slots stuck in_production with expired leases and safely reset or fail them."""
        cursor = self.collection.find({
            "status": "in_production",
            "lease_expires_at": {"$lt": now_utc}
        })
        expired_slots = await cursor.to_list(length=100)
        reclaimed_count = 0
        for slot in expired_slots:
            attempts = slot.get("attempts", 0)
            max_attempts = slot.get("max_attempts", 3)
            oid = slot["_id"]
            if attempts >= max_attempts:
                await self.collection.update_one(
                    {"_id": oid},
                    {
                        "$set": {
                            "status": "failed",
                            "failure_reason": "LEASE_EXPIRED_MAX_ATTEMPTS",
                            "claimed_by": None,
                            "lease_expires_at": None,
                            "updated_at": now_utc
                        }
                    }
                )
            else:
                await self.collection.update_one(
                    {"_id": oid},
                    {
                        "$set": {
                            "status": "pending",
                            "claimed_by": None,
                            "lease_expires_at": None,
                            "updated_at": now_utc
                        }
                    }
                )
            reclaimed_count += 1
        return reclaimed_count

    async def count_active_channel_slots(self, channel_id: str) -> int:
        """Count active in_production slots for channel concurrency control."""
        return await self.collection.count_documents({
            "channel_id": channel_id,
            "status": "in_production"
        })


class NicheCacheRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "niche_recommendations_cache")

    async def get_cached(self, channel_id: str, context_hash: str) -> dict | None:
        now = datetime.now(timezone.utc)
        return await self.collection.find_one({
            "channel_id": channel_id,
            "context_hash": context_hash,
            "expires_at": {"$gt": now}
        })

    async def save_cache(self, channel_id: str, user_id: str, context_hash: str, recommendations: list[dict], ttl_seconds: int = 86400) -> str:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        doc = {
            "channel_id": channel_id,
            "user_id": user_id,
            "context_hash": context_hash,
            "recommendations": recommendations,
            "created_at": now,
            "expires_at": expires_at
        }
        res = await self.collection.update_one(
            {"channel_id": channel_id},
            {"$set": doc},
            upsert=True
        )
        return str(res.upserted_id or "")

    async def invalidate(self, channel_id: str) -> bool:
        res = await self.collection.delete_many({"channel_id": channel_id})
        return res.deleted_count > 0
