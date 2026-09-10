import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.publishing_service import PublishingService
from backend.app.youtube.client import YouTubeAPIError

@pytest.mark.asyncio
async def test_create_scheduled_publishing_job():
    mock_db = MagicMock()
    service = PublishingService(mock_db)

    service.video_repo.find_by_id = AsyncMock(return_value={
        "_id": "507f1f77bcf86cd799439011",
        "channel_id": "chan_123",
        "title": "Scheduled Short"
    })
    service.pub_repo.insert_one = AsyncMock(return_value="pub_job_999")

    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    job = await service.create_publishing_job(
        user_id="user_1",
        video_id="507f1f77bcf86cd799439011",
        platform="youtube",
        metadata={"title": "Scheduled Video Title"},
        scheduled_at=future_time
    )

    assert job["status"] == "scheduled"
    assert job["id"] == "pub_job_999"
    service.pub_repo.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_publishing_calendar():
    mock_db = MagicMock()
    service = PublishingService(mock_db)

    service.pub_repo.find_many = AsyncMock(return_value=[
        {
            "_id": "job_1",
            "video_id": "vid_1",
            "metadata": {"title": "Drop 1"},
            "status": "scheduled",
            "scheduled_at": datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc),
            "platform": "youtube"
        }
    ])
    service.video_repo.find_many = AsyncMock(return_value=[
        {
            "_id": "vid_1",
            "title": "Drop 1",
            "thumbnail_path": "media/thumbnails/vid_1.jpg"
        }
    ])

    calendar = await service.get_publishing_calendar(user_id="user_1")
    assert len(calendar) == 1
    assert calendar[0]["title"] == "Drop 1"
    assert calendar[0]["status"] == "scheduled"
    assert "2026-09-15" in calendar[0]["date"]

@pytest.mark.asyncio
async def test_execute_publish_requires_oauth():
    mock_db = MagicMock()
    service = PublishingService(mock_db)

    service.pub_repo.find_by_id = AsyncMock(return_value={"_id": "j1", "video_id": "v1"})
    service.video_repo.find_by_id = AsyncMock(return_value={"_id": "v1", "title": "Vid"})
    service.pub_repo.mark_failed = AsyncMock(return_value=True)

    with patch("backend.app.services.publishing_service.get_youtube_client_for_user", AsyncMock(return_value=None)):
        with pytest.raises(YouTubeAPIError) as exc:
            await service.execute_publish(user_id="user_unconnected", job_id="j1")
        assert exc.value.error_code == "GOOGLE_OAUTH_NOT_CONFIGURED"
        service.pub_repo.mark_failed.assert_called_once()
