import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app

@pytest.mark.asyncio
async def test_health_check_endpoints(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Consolidated health check
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert "mongodb" in data["services"]
        assert "ollama" in data["services"]
        assert "ffmpeg" in data["services"]
        
        # 2. Video subsystem health check
        video_resp = await client.get("/api/health/video")
        assert video_resp.status_code == 200
        video_data = video_resp.json()
        assert video_data["status"] == "ok"
        assert "ffmpeg" in video_data
        assert "ffprobe" in video_data

        # 3. Ollama health check (gracefully returns 200 with degraded/unavailable when offline)
        ollama_resp = await client.get("/api/health/ollama")
        assert ollama_resp.status_code == 200
        ollama_data = ollama_resp.json()
        assert "status" in ollama_data
