import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from tests.fixtures.sample_data import SAMPLE_USER_A, SAMPLE_USER_B, SAMPLE_CHANNEL_A, SAMPLE_CHANNEL_B

@pytest.mark.asyncio
async def test_multi_tenant_channel_and_resource_isolation(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register User A
        resp = await client.post("/api/auth/register", json=SAMPLE_USER_A)
        assert resp.status_code == 201
        token_a = resp.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Register User B
        resp = await client.post("/api/auth/register", json=SAMPLE_USER_B)
        assert resp.status_code == 201
        token_b = resp.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 3. User A creates Channel A
        resp = await client.post("/api/channels/", json=SAMPLE_CHANNEL_A, headers=headers_a)
        assert resp.status_code == 201
        channel_a_id = resp.json()["id"]

        # 4. User B lists channels - must NOT see Channel A
        resp = await client.get("/api/channels/", headers=headers_b)
        assert resp.status_code == 200
        b_channels = resp.json()
        assert len(b_channels) == 0

        # 5. User B attempts to access Channel A directly -> 404
        resp = await client.get(f"/api/channels/{channel_a_id}", headers=headers_b)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "HTTP_404"

        # 6. User B attempts to update Channel A -> 404
        resp = await client.put(f"/api/channels/{channel_a_id}", json={"name": "Hacked Channel"}, headers=headers_b)
        assert resp.status_code == 404

        # 7. User B attempts to delete Channel A -> 404
        resp = await client.delete(f"/api/channels/{channel_a_id}", headers=headers_b)
        assert resp.status_code == 404

        # Verify Channel A name is unchanged for User A
        resp = await client.get(f"/api/channels/{channel_a_id}", headers=headers_a)
        assert resp.status_code == 200
        assert resp.json()["name"] == SAMPLE_CHANNEL_A["name"]

        # 8. User B creates Channel B
        resp = await client.post("/api/channels/", json=SAMPLE_CHANNEL_B, headers=headers_b)
        assert resp.status_code == 201
        channel_b_id = resp.json()["id"]

        # 9. Verify each user sees only their own channel in list
        resp_a = await client.get("/api/channels/", headers=headers_a)
        ids_a = [c["id"] for c in resp_a.json()]
        assert channel_a_id in ids_a
        assert channel_b_id not in ids_a

        resp_b = await client.get("/api/channels/", headers=headers_b)
        ids_b = [c["id"] for c in resp_b.json()]
        assert channel_b_id in ids_b
        assert channel_a_id not in ids_b
