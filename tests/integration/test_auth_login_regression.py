import pytest
import json
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from tests.fixtures.sample_data import SAMPLE_USER_A

@pytest.mark.asyncio
async def test_auth_login_regression(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register user first
        reg_resp = await client.post("/api/auth/register", json=SAMPLE_USER_A)
        assert reg_resp.status_code in (201, 400)

        # 1. Valid JSON login with 'email'
        resp = await client.post("/api/auth/login", json={
            "email": SAMPLE_USER_A["email"],
            "password": SAMPLE_USER_A["password"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # 2. Valid JSON login with 'username' alias
        resp = await client.post("/api/auth/login", json={
            "username": SAMPLE_USER_A["email"],
            "password": SAMPLE_USER_A["password"]
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

        # 3. application/x-www-form-urlencoded payload must return clean 422, NEVER secondary 500
        raw_form = f"username={SAMPLE_USER_A['email']}&password={SAMPLE_USER_A['password']}"
        resp = await client.post(
            "/api/auth/login",
            content=raw_form.encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"
        # Verify no raw passwords leaked in error payload
        assert SAMPLE_USER_A["password"] not in json.dumps(body)

        # 4. Bad password -> 401
        resp = await client.post("/api/auth/login", json={
            "email": SAMPLE_USER_A["email"],
            "password": "CompletelyWrongPassword!"
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

        # 5. Nonexistent user -> 401
        resp = await client.post("/api/auth/login", json={
            "email": "nonexistent_ghost_user@example.com",
            "password": "SomePassword123!"
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

        # 6. Missing password -> 422
        resp = await client.post("/api/auth/login", json={
            "email": SAMPLE_USER_A["email"]
        })
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

        # 7. Redaction check on malformed validation
        secret_attempt = "SuperSecretPasswordP@ssword999!"
        resp = await client.post("/api/auth/login", json={
            "email": "notanemail",
            "password": secret_attempt
        })
        assert resp.status_code == 422
        resp_text = resp.text
        assert secret_attempt not in resp_text
