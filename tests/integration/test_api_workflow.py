import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.repositories.jobs import JobRepository
from backend.app.repositories.videos import VideoRepository
from backend.app.repositories.analytics import AnalyticsRepository
from tests.fixtures.sample_data import (
    SAMPLE_USER_A,
    SAMPLE_CHANNEL_A,
    SAMPLE_SCRIPT,
    SAMPLE_ANALYTICS_SNAPSHOT
)

@pytest.mark.asyncio
async def test_complete_creator_workflow(test_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register and login
        resp = await client.post("/api/auth/register", json={
            "email": "workflow_creator@example.com",
            "password": "Password123!Secure",
            "name": "Workflow Creator"
        })
        assert resp.status_code == 201
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get profile
        me_resp = await client.get("/api/auth/me", headers=headers)
        user_id = me_resp.json()["id"]

        # 3. Create a Channel
        resp = await client.post("/api/channels/", json=SAMPLE_CHANNEL_A, headers=headers)
        assert resp.status_code == 201
        channel = resp.json()
        channel_id = channel["id"]
        assert channel["name"] == SAMPLE_CHANNEL_A["name"]

        # 4. Create Content Idea
        idea_payload = {
            "channel_id": channel_id,
            "title": "5 Breakthrough AI Coding Assistants in 2026",
            "description": "Explaining the architecture behind next-gen coding agents.",
            "keywords": ["AI", "Coding", "Agents", "Future"],
            "target_audience": "Software Developers"
        }
        resp = await client.post("/api/content/ideas", json=idea_payload, headers=headers)
        assert resp.status_code == 201
        idea_id = resp.json()["id"]

        # List ideas
        resp = await client.get(f"/api/content/ideas?channel_id={channel_id}", headers=headers)
        assert resp.status_code == 200
        ideas = resp.json()
        assert len(ideas) >= 1
        assert any(i["id"] == idea_id for i in ideas)

        # Update idea status
        resp = await client.put(f"/api/content/ideas/{idea_id}/status", json={"status": "approved"}, headers=headers)
        assert resp.status_code == 200

        # 5. Create a Script
        script_payload = {
            "channel_id": channel_id,
            "topic": "5 Breakthrough AI Coding Assistants in 2026",
            "title": "5 Breakthrough AI Coding Assistants in 2026",
            "script_text": "Autonomous coding agents are reshaping software engineering.",
            "content_idea_id": idea_id
        }
        resp = await client.post("/api/content/scripts", json=script_payload, headers=headers)
        assert resp.status_code == 201
        script_id = resp.json()["id"]

        # 6. Queue a Video Generation Job
        video_gen_payload = {
            "channel_id": channel_id,
            "request_data": {
                "topic": "AI Coding Agents",
                "script": "Autonomous coding agents are reshaping software engineering.",
                "duration": 30,
                "aspect_ratio": "9:16",
                "script_id": script_id
            }
        }
        resp = await client.post("/api/videos/generate", json=video_gen_payload, headers=headers)
        assert resp.status_code == 201
        video_job_data = resp.json()
        job_id = video_job_data["job_id"]
        video_id = video_job_data["video_id"]
        assert job_id is not None
        assert video_id is not None

        # 7. Check Job Listing and Status
        resp = await client.get("/api/jobs/", headers=headers)
        assert resp.status_code == 200
        user_jobs = resp.json()
        assert any(j["id"] == job_id for j in user_jobs)

        resp = await client.get(f"/api/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] in ["queued", "processing"]

        # 8. Check Video Listing
        resp = await client.get(f"/api/videos/?channel_id={channel_id}", headers=headers)
        assert resp.status_code == 200
        videos = resp.json()
        assert any(v["id"] == video_id for v in videos)

        # 9. Stale Job Worker Recovery Verification
        job_repo = JobRepository(test_db)
        # Create a simulated stuck job that crashed 20 minutes ago
        stuck_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        stuck_job_id = await job_repo.enqueue(
            job_type="video_generation",
            user_id=user_id,
            channel_id=channel_id,
            payload={"simulated": "crash"}
        )
        # Mark as processing with old timestamp
        from backend.app.repositories.base import safe_object_id
        await test_db.jobs.update_one(
            {"_id": safe_object_id(stuck_job_id)},
            {"$set": {"status": "processing", "updated_at": stuck_time, "started_at": stuck_time}}
        )
        
        # Trigger stale recovery
        recovered_count = await job_repo.recover_stale_jobs(timeout_minutes=15)
        assert recovered_count >= 1

        recovered_job = await job_repo.find_by_id(stuck_job_id)
        assert recovered_job["status"] == "queued"
        assert recovered_job["attempts"] >= 1

        # 10. Analytics Recording & Retrieval
        analytics_repo = AnalyticsRepository(test_db)
        await analytics_repo.create_snapshot({
            "user_id": user_id,
            "channel_id": channel_id,
            "video_id": video_id,
            **SAMPLE_ANALYTICS_SNAPSHOT,
            "snapshot_date": datetime.now(timezone.utc)
        })

        resp = await client.get(f"/api/analytics/channel/{channel_id}", headers=headers)
        assert resp.status_code == 200
        analytics_list = resp.json()
        assert len(analytics_list) >= 1
        assert analytics_list[0]["views"] == 4500
