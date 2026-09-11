import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from backend.app.database import db_manager
from backend.app.config import get_settings
from backend.app.youtube.client import (
    YouTubeClient,
    YouTubeAPIError,
    get_youtube_client_for_channel,
    get_youtube_client_for_user
)
from backend.app.auth.service import AuthService


@pytest.mark.asyncio
async def test_multi_account_oauth_isolation_and_ownership():
    """Verify 1 user -> multiple Google accounts -> multiple YouTube channels
    with strict credential isolation and cross-tenant invariant protection.
    """
    await db_manager.connect()
    db = db_manager.get_database()
    settings = get_settings()
    fernet = settings.get_fernet()

    user1_id = "user_oauth_iso_1"
    user2_id = "user_oauth_iso_2"

    # Clean up prior test records
    await db.oauth_accounts.delete_many({"user_id": {"$in": [user1_id, user2_id]}})
    await db.channels.delete_many({"user_id": {"$in": [user1_id, user2_id]}})

    now = datetime.now(timezone.utc)

    # 1. Setup User 1 Google Account A
    acc_a_token = "access_token_google_account_A"
    acc_a_refresh = "refresh_token_google_account_A"
    acc_a_res = await db.oauth_accounts.insert_one({
        "user_id": user1_id,
        "provider": "google",
        "provider_account_id": "google_sub_acc_a",
        "email": "creator_a@example.com",
        "name": "Creator Account A",
        "status": "connected",
        "access_token_encrypted": fernet.encrypt(acc_a_token.encode()).decode(),
        "refresh_token_encrypted": fernet.encrypt(acc_a_refresh.encode()).decode(),
        "token_expires_at": now + timedelta(hours=1),
        "granted_scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
        "created_at": now,
        "updated_at": now
    })
    acc_a_id = str(acc_a_res.inserted_id)

    # 2. Setup User 1 Google Account B
    acc_b_token = "access_token_google_account_B"
    acc_b_refresh = "refresh_token_google_account_B"
    acc_b_res = await db.oauth_accounts.insert_one({
        "user_id": user1_id,
        "provider": "google",
        "provider_account_id": "google_sub_acc_b",
        "email": "creator_b@example.com",
        "name": "Creator Account B",
        "status": "connected",
        "access_token_encrypted": fernet.encrypt(acc_b_token.encode()).decode(),
        "refresh_token_encrypted": fernet.encrypt(acc_b_refresh.encode()).decode(),
        "token_expires_at": now + timedelta(hours=1),
        "granted_scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
        "created_at": now,
        "updated_at": now
    })
    acc_b_id = str(acc_b_res.inserted_id)

    # 3. Setup User 2 Google Account (Different Tenant)
    acc_user2_token = "access_token_user2"
    acc_user2_res = await db.oauth_accounts.insert_one({
        "user_id": user2_id,
        "provider": "google",
        "provider_account_id": "google_sub_user2",
        "email": "user2@example.com",
        "name": "User 2 Account",
        "status": "connected",
        "access_token_encrypted": fernet.encrypt(acc_user2_token.encode()).decode(),
        "token_expires_at": now + timedelta(hours=1),
        "granted_scopes": ["https://www.googleapis.com/auth/youtube.readonly"],
        "created_at": now,
        "updated_at": now
    })
    acc_user2_id = str(acc_user2_res.inserted_id)

    # 4. Attach Channel A1 and Channel A2 to Account A
    ch_a1_res = await db.channels.insert_one({
        "user_id": user1_id,
        "oauth_account_id": acc_a_id,
        "google_account_email": "creator_a@example.com",
        "name": "Channel A1 - Gaming",
        "youtube_channel_id": "UC_channel_a1",
        "status": "connected",
        "autopilot_enabled": True,
        "created_at": now,
        "updated_at": now
    })
    ch_a1_id = str(ch_a1_res.inserted_id)

    ch_a2_res = await db.channels.insert_one({
        "user_id": user1_id,
        "oauth_account_id": acc_a_id,
        "google_account_email": "creator_a@example.com",
        "name": "Channel A2 - Highlights",
        "youtube_channel_id": "UC_channel_a2",
        "status": "connected",
        "autopilot_enabled": False,
        "created_at": now,
        "updated_at": now
    })
    ch_a2_id = str(ch_a2_res.inserted_id)

    # 5. Attach Channel B1 to Account B
    ch_b1_res = await db.channels.insert_one({
        "user_id": user1_id,
        "oauth_account_id": acc_b_id,
        "google_account_email": "creator_b@example.com",
        "name": "Channel B1 - Tech Insights",
        "youtube_channel_id": "UC_channel_b1",
        "status": "connected",
        "autopilot_enabled": True,
        "created_at": now,
        "updated_at": now
    })
    ch_b1_id = str(ch_b1_res.inserted_id)

    try:
        # TEST A: Credential resolution isolation
        client_a1 = await get_youtube_client_for_channel(ch_a1_id, user1_id, db)
        assert client_a1.access_token == acc_a_token
        assert client_a1.refresh_token == acc_a_refresh

        client_a2 = await get_youtube_client_for_channel(ch_a2_id, user1_id, db)
        assert client_a2.access_token == acc_a_token
        assert client_a2.refresh_token == acc_a_refresh

        client_b1 = await get_youtube_client_for_channel(ch_b1_id, user1_id, db)
        assert client_b1.access_token == acc_b_token
        assert client_b1.refresh_token == acc_b_refresh

        # TEST B: Invariant Protection — User 2 cannot access Channel A1
        with pytest.raises(YouTubeAPIError) as exc_info:
            await get_youtube_client_for_channel(ch_a1_id, user2_id, db)
        assert exc_info.value.status_code == 403
        assert exc_info.value.error_code == "CHANNEL_FORBIDDEN"

        # TEST C: Invariant Protection — Corrupt Channel owned by User 1 pointing to User 2 OAuth Account
        corrupted_ch_res = await db.channels.insert_one({
            "user_id": user1_id,
            "oauth_account_id": acc_user2_id,  # Points to User 2's credentials!
            "name": "Exploit Channel",
            "youtube_channel_id": "UC_exploit",
            "status": "connected",
            "created_at": now,
            "updated_at": now
        })
        corrupted_ch_id = str(corrupted_ch_res.inserted_id)

        with pytest.raises(YouTubeAPIError) as exc_info:
            await get_youtube_client_for_channel(corrupted_ch_id, user1_id, db)
        assert exc_info.value.status_code == 403
        assert exc_info.value.error_code == "OAUTH_OWNERSHIP_MISMATCH"

        # TEST D: Nonexistent OAuth Account ID on channel
        bogus_ch_res = await db.channels.insert_one({
            "user_id": user1_id,
            "oauth_account_id": str(ObjectId()),
            "name": "Bogus OAuth Channel",
            "youtube_channel_id": "UC_bogus",
            "status": "connected",
            "created_at": now,
            "updated_at": now
        })
        bogus_ch_id = str(bogus_ch_res.inserted_id)

        with pytest.raises(YouTubeAPIError) as exc_info:
            await get_youtube_client_for_channel(bogus_ch_id, user1_id, db)
        assert exc_info.value.status_code == 404
        assert exc_info.value.error_code == "OAUTH_ACCOUNT_NOT_FOUND"

        # TEST E: Legacy Migration — Channel with oauth_account_id = None
        legacy_ch_res = await db.channels.insert_one({
            "user_id": user1_id,
            "name": "Legacy Channel Without OAuth ID",
            "youtube_channel_id": "UC_legacy_channel",
            "status": "connected",
            "created_at": now,
            "updated_at": now
        })
        legacy_ch_id = str(legacy_ch_res.inserted_id)

        client_legacy = await get_youtube_client_for_channel(legacy_ch_id, user1_id, db)
        assert client_legacy.access_token in (acc_a_token, acc_b_token)

        # Check DB was auto-migrated
        migrated = await db.channels.find_one({"_id": ObjectId(legacy_ch_id)})
        assert migrated.get("oauth_account_id") is not None
        assert migrated.get("google_account_email") is not None

        # TEST F: Safe Disconnect Semantics — Disconnect Account A
        auth_service = AuthService(db, settings)
        disconnect_success = await auth_service.disconnect_oauth_account(user1_id, acc_a_id)
        assert disconnect_success is True

        # Verify Account A is disconnected
        acc_a_after = await db.oauth_accounts.find_one({"_id": ObjectId(acc_a_id)})
        assert acc_a_after["status"] == "disconnected"

        # Verify Channel A1 & A2 are disconnected and autopilot disabled, but NOT deleted
        ch_a1_after = await db.channels.find_one({"_id": ObjectId(ch_a1_id)})
        assert ch_a1_after is not None
        assert ch_a1_after["status"] == "disconnected"
        assert ch_a1_after["autopilot_enabled"] is False

        ch_a2_after = await db.channels.find_one({"_id": ObjectId(ch_a2_id)})
        assert ch_a2_after is not None
        assert ch_a2_after["status"] == "disconnected"

        # Client resolution for disconnected Channel A1 must fail
        with pytest.raises(YouTubeAPIError) as exc_info:
            await get_youtube_client_for_channel(ch_a1_id, user1_id, db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.error_code in ("CHANNEL_DISCONNECTED", "YOUTUBE_DISCONNECTED")

        # Account B and Channel B1 must remain completely unaffected
        ch_b1_after = await db.channels.find_one({"_id": ObjectId(ch_b1_id)})
        assert ch_b1_after["status"] == "connected"
        assert ch_b1_after["autopilot_enabled"] is True

        client_b1_after = await get_youtube_client_for_channel(ch_b1_id, user1_id, db)
        assert client_b1_after.access_token == acc_b_token

    finally:
        # Cleanup
        await db.oauth_accounts.delete_many({"user_id": {"$in": [user1_id, user2_id]}})
        await db.channels.delete_many({"user_id": {"$in": [user1_id, user2_id]}})


@pytest.mark.asyncio
async def test_concurrent_token_refresh_safety():
    """Verify concurrent token refresh callbacks on different OAuth accounts do not collide."""
    await db_manager.connect()
    db = db_manager.get_database()
    settings = get_settings()
    fernet = settings.get_fernet()

    user_id = "user_concurrent_refresh"
    await db.oauth_accounts.delete_many({"user_id": user_id})
    await db.channels.delete_many({"user_id": user_id})

    now = datetime.now(timezone.utc)

    # Insert Account 1
    acc1_res = await db.oauth_accounts.insert_one({
        "user_id": user_id,
        "provider": "google",
        "provider_account_id": "google_acc_1",
        "email": "acc1@example.com",
        "status": "connected",
        "access_token_encrypted": fernet.encrypt(b"token1_old").decode(),
        "created_at": now,
        "updated_at": now
    })
    acc1_id = str(acc1_res.inserted_id)

    # Insert Account 2
    acc2_res = await db.oauth_accounts.insert_one({
        "user_id": user_id,
        "provider": "google",
        "provider_account_id": "google_acc_2",
        "email": "acc2@example.com",
        "status": "connected",
        "access_token_encrypted": fernet.encrypt(b"token2_old").decode(),
        "created_at": now,
        "updated_at": now
    })
    acc2_id = str(acc2_res.inserted_id)

    ch1_res = await db.channels.insert_one({
        "user_id": user_id,
        "oauth_account_id": acc1_id,
        "name": "Ch 1",
        "youtube_channel_id": "UC_ch1",
        "status": "connected",
        "created_at": now,
        "updated_at": now
    })
    ch1_id = str(ch1_res.inserted_id)

    ch2_res = await db.channels.insert_one({
        "user_id": user_id,
        "oauth_account_id": acc2_id,
        "name": "Ch 2",
        "youtube_channel_id": "UC_ch2",
        "status": "connected",
        "created_at": now,
        "updated_at": now
    })
    ch2_id = str(ch2_res.inserted_id)

    try:
        client1 = await get_youtube_client_for_channel(ch1_id, user_id, db)
        client2 = await get_youtube_client_for_channel(ch2_id, user_id, db)

        # Trigger simulated refresh callback concurrently
        async def refresh_c1():
            await client1.token_refreshed_callback("token1_NEW", 3600)

        async def refresh_c2():
            await client2.token_refreshed_callback("token2_NEW", 3600)

        await asyncio.gather(refresh_c1(), refresh_c2())

        # Verify DB state
        doc1 = await db.oauth_accounts.find_one({"_id": ObjectId(acc1_id)})
        doc2 = await db.oauth_accounts.find_one({"_id": ObjectId(acc2_id)})

        decrypted1 = fernet.decrypt(doc1["access_token_encrypted"].encode()).decode()
        decrypted2 = fernet.decrypt(doc2["access_token_encrypted"].encode()).decode()

        assert decrypted1 == "token1_NEW"
        assert decrypted2 == "token2_NEW"

    finally:
        await db.oauth_accounts.delete_many({"user_id": user_id})
        await db.channels.delete_many({"user_id": user_id})

