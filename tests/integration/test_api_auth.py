import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from tests.fixtures.sample_data import SAMPLE_USER_A, SAMPLE_USER_B

@pytest.mark.asyncio
async def test_auth_full_lifecycle(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Invalid email format (422)
        resp = await client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "ValidPassword123!",
            "name": "Invalid User"
        })
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

        # 2. Short password (< 8 chars) (422)
        resp = await client.post("/api/auth/register", json={
            "email": "short_pw@test.com",
            "password": "short",
            "name": "Short Password User"
        })
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

        # 3. Successful Registration (User A)
        resp = await client.post("/api/auth/register", json=SAMPLE_USER_A)
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        access_token_a = data["access_token"]
        refresh_token_a = data["refresh_token"]

        # 4. Duplicate Registration (User A again -> 400 ALREADY_EXISTS)
        resp = await client.post("/api/auth/register", json=SAMPLE_USER_A)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "EMAIL_EXISTS"

        # 5. Access /api/auth/me with valid token
        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token_a}"})
        assert resp.status_code == 200
        me = resp.json()
        assert me["email"] == SAMPLE_USER_A["email"]
        assert me["name"] == SAMPLE_USER_A["name"]
        user_a_id = me["id"]
        assert user_a_id is not None

        # 6. Access /api/auth/me with invalid token -> 401
        resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_xyz"})
        assert resp.status_code == 401
        assert "error" in resp.json()

        # 7. Login with bad password -> 401
        resp = await client.post("/api/auth/login", json={
            "email": SAMPLE_USER_A["email"],
            "password": "WrongPassword123!"
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

        # 8. Login with correct credentials
        resp = await client.post("/api/auth/login", json={
            "email": SAMPLE_USER_A["email"],
            "password": SAMPLE_USER_A["password"]
        })
        assert resp.status_code == 200
        login_data = resp.json()
        assert "access_token" in login_data
        new_refresh = login_data["refresh_token"]

        # 9. Refresh token rotation
        resp = await client.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        assert resp.status_code == 200
        rotated = resp.json()
        assert "access_token" in rotated
        assert "refresh_token" in rotated
        rotated_refresh = rotated["refresh_token"]

        # 10. Replay of old refresh token must be rejected (revoked) -> 401
        resp = await client.post("/api/auth/refresh", json={"refresh_token": new_refresh})
        assert resp.status_code == 401

        # 11. Logout using current refresh token
        resp = await client.post("/api/auth/logout", json={"refresh_token": rotated_refresh})
        assert resp.status_code == 200
        assert resp.json().get("success") is True

        # 12. Using revoked refresh token after logout -> 401
        resp = await client.post("/api/auth/refresh", json={"refresh_token": rotated_refresh})
        assert resp.status_code == 401

        # 13. Forgot and Reset Password flow
        resp = await client.post("/api/auth/forgot-password", json={"email": SAMPLE_USER_A["email"]})
        assert resp.status_code == 200
        reset_token = resp.json().get("reset_token")
        assert reset_token is not None

        new_password = "NewlyUpdatedPassword2026!"
        resp = await client.post("/api/auth/reset-password", json={
            "token": reset_token,
            "new_password": new_password
        })
        assert resp.status_code == 200
        assert resp.json().get("success") is True

        # Verify login works with new password
        resp = await client.post("/api/auth/login", json={
            "email": SAMPLE_USER_A["email"],
            "password": new_password
        })
        assert resp.status_code == 200
