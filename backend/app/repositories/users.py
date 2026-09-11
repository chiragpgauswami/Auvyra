from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.app.repositories.base import BaseRepository
from datetime import datetime, timezone
from bson import ObjectId

class UserRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")

    async def find_by_email(self, email: str) -> dict | None:
        return await self.collection.find_one({"email": email})

    async def create_user(self, user_data: dict) -> str:
        return await self.insert_one(user_data)

    async def verify_email(self, user_id: str) -> bool:
        return await self.update_one(user_id, {"email_verified": True})

    async def update_password(self, user_id: str, password_hash: str) -> bool:
        return await self.update_one(user_id, {"password_hash": password_hash})


class OAuthAccountRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "oauth_accounts")

    async def find_by_provider(self, user_id: str, provider: str) -> dict | None:
        return await self.collection.find_one({"user_id": user_id, "provider": provider, "status": {"$ne": "disconnected"}})

    async def find_all_by_user(self, user_id: str, provider: str = "google") -> list[dict]:
        cursor = self.collection.find({"user_id": user_id, "provider": provider})
        return await cursor.to_list(length=100)

    async def find_by_account_id(self, user_id: str, provider: str, provider_account_id: str) -> dict | None:
        return await self.collection.find_one({
            "user_id": user_id,
            "provider": provider,
            "provider_account_id": provider_account_id
        })

    async def find_by_provider_account_id(self, provider: str, provider_account_id: str) -> dict | None:
        return await self.collection.find_one({
            "provider": provider,
            "provider_account_id": provider_account_id
        })

    async def find_by_id(self, account_id: str, user_id: str | None = None) -> dict | None:
        query = {"_id": ObjectId(account_id)}
        if user_id:
            query["user_id"] = user_id
        return await self.collection.find_one(query)

    async def upsert_account(self, user_id: str, provider: str, provider_account_id: str, data: dict) -> str:
        existing = await self.find_by_account_id(user_id, provider, provider_account_id)
        if existing:
            await self.update_one(str(existing["_id"]), data)
            return str(existing["_id"])
        
        data["user_id"] = user_id
        data["provider"] = provider
        data["provider_account_id"] = provider_account_id
        return await self.insert_one(data)

    async def upsert(self, user_id: str, provider: str, data: dict) -> str:
        provider_account_id = data.get("provider_account_id")
        if provider_account_id:
            return await self.upsert_account(user_id, provider, provider_account_id, data)
        existing = await self.find_by_provider(user_id, provider)
        if existing:
            await self.update_one(str(existing["_id"]), data)
            return str(existing["_id"])
        
        data["user_id"] = user_id
        data["provider"] = provider
        return await self.insert_one(data)

    async def disconnect_account(self, account_id: str, user_id: str) -> bool:
        """Mark OAuth account as disconnected, preserving history."""
        result = await self.collection.update_one(
            {"_id": ObjectId(account_id), "user_id": user_id},
            {"$set": {"status": "disconnected", "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0


class SessionRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "sessions")

    async def create_session(self, user_id: str, refresh_token_hash: str, expires_at: datetime) -> str:
        return await self.insert_one({
            "user_id": user_id,
            "refresh_token_hash": refresh_token_hash,
            "expires_at": expires_at,
            "is_valid": True
        })

    async def find_valid_session(self, refresh_token_hash: str) -> dict | None:
        return await self.collection.find_one({
            "refresh_token_hash": refresh_token_hash,
            "is_valid": True,
            "expires_at": {"$gt": datetime.now(timezone.utc)}
        })

    async def revoke_session(self, session_id: str) -> bool:
        return await self.update_one(session_id, {"is_valid": False})

    async def revoke_all_user_sessions(self, user_id: str) -> int:
        result = await self.collection.update_many(
            {"user_id": user_id, "is_valid": True},
            {"$set": {"is_valid": False, "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count
