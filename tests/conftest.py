import os
import pytest
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.config import get_settings
from backend.app.database import db_manager

TEST_DB_NAME = "auvyra_test"


@pytest.fixture(scope="session")
async def init_test_db():
    settings = get_settings()
    # Connect db_manager directly to test database
    await db_manager.connect(settings.MONGODB_URI, TEST_DB_NAME)
    await db_manager.create_indexes()
    
    yield db_manager.get_database()
    
    # Cleanup test database on teardown
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    await client.drop_database(TEST_DB_NAME)
    await db_manager.disconnect()

@pytest.fixture
async def test_db(init_test_db):
    db = init_test_db
    # Clean all collections before each test
    collections = await db.list_collection_names()
    for col in collections:
        if not col.startswith("system."):
            await db[col].delete_many({})
    return db

@pytest.fixture
async def async_client(init_test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
