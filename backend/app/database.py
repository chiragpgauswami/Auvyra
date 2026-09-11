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
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = AsyncIOMotorClient(target_uri)
        self.db = self.client[target_db]

    async def disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def get_database(self) -> AsyncIOMotorDatabase:
        if self.db is None or self.client is None:
            settings = get_settings()
            self.client = AsyncIOMotorClient(settings.MONGODB_URI)
            self.db = self.client[settings.MONGODB_DATABASE]
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

            # channel_brains: compound (user_id, channel_id) (unique)
            await self.db.channel_brains.create_index([("user_id", pymongo.ASCENDING), ("channel_id", pymongo.ASCENDING)], unique=True)

            # autopilot_queue: compound (channel_id, scheduled_at) and (channel_id, status)
            await self.db.autopilot_queue.create_index([("channel_id", pymongo.ASCENDING), ("scheduled_at", pymongo.ASCENDING)])
            await self.db.autopilot_queue.create_index([("user_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
            await self.db.autopilot_queue.create_index([("channel_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])

            # niche_recommendations_cache: channel_id
            await self.db.niche_recommendations_cache.create_index([("channel_id", pymongo.ASCENDING)], unique=True)
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise

db_manager = MongoDBManager()

def get_db() -> AsyncIOMotorDatabase:
    return db_manager.get_database()
