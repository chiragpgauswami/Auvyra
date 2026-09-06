import pymongo
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger

from backend.app.config import get_settings

class MongoDBManager:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    async def connect(self, uri: str = None, database: str = None):
        settings = get_settings()
        target_uri = uri or settings.MONGODB_URI
        target_db = database or settings.MONGODB_DATABASE
        self.client = AsyncIOMotorClient(target_uri)
        self.db = self.client[target_db]

    async def disconnect(self):
        if self.client:
            self.client.close()

    def get_database(self) -> AsyncIOMotorDatabase:
        if self.db is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return self.db

    async def create_indexes(self):
        if self.db is None:
            raise RuntimeError("Database not initialized.")

        try:
            # users.email (unique)
            await self.db.users.create_index("email", unique=True)
            
            # oauth_accounts.user_id
            await self.db.oauth_accounts.create_index("user_id")
            
            # channels.user_id
            await self.db.channels.create_index("user_id")
            
            # channels.youtube_channel_id (unique, sparse)
            await self.db.channels.create_index("youtube_channel_id", unique=True, sparse=True)
            
            # content_ideas: compound (channel_id, status)
            await self.db.content_ideas.create_index([("channel_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
            
            # videos: compound (channel_id, status) AND compound (channel_id, published_at descending)
            await self.db.videos.create_index([("channel_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
            await self.db.videos.create_index([("channel_id", pymongo.ASCENDING), ("published_at", pymongo.DESCENDING)])
            
            # analytics_snapshots: compound (channel_id, video_id)
            await self.db.analytics_snapshots.create_index([("channel_id", pymongo.ASCENDING), ("video_id", pymongo.ASCENDING)])
            
            # jobs: compound (status, created_at)
            await self.db.jobs.create_index([("status", pymongo.ASCENDING), ("created_at", pymongo.ASCENDING)])
            
            # strategy_insights.channel_id
            await self.db.strategy_insights.create_index("channel_id")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise

db_manager = MongoDBManager()

def get_db() -> AsyncIOMotorDatabase:
    return db_manager.get_database()
