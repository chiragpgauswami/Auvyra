import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.analytics_service import AnalyticsService
from backend.app.youtube.client import YouTubeAPIError

@pytest.mark.asyncio
async def test_analytics_sync_blocks_unconnected():
    mock_db = MagicMock()
    service = AnalyticsService(mock_db)

    service.channel_repo.find_by_id = AsyncMock(return_value={
        "_id": "chan_1",
        "user_id": "u1",
        "youtube_channel_id": "UC123"
    })

    with patch("backend.app.services.analytics_service.get_youtube_client_for_user", AsyncMock(return_value=None)):
        with pytest.raises(YouTubeAPIError) as exc:
            await service.sync_channel_analytics("u1", "chan_1")
        assert exc.value.error_code == "GOOGLE_OAUTH_NOT_CONFIGURED"

@pytest.mark.asyncio
async def test_analytics_sync_ingests_real_tabular_data():
    mock_db = MagicMock()
    service = AnalyticsService(mock_db)

    service.channel_repo.find_by_id = AsyncMock(return_value={
        "_id": "chan_1",
        "user_id": "u1",
        "youtube_channel_id": "UC_REAL_CHANNEL"
    })

    mock_yt = MagicMock()
    mock_yt.access_token = "valid_token"
    mock_yt.get_channel_reports = AsyncMock(return_value={
        "columnHeaders": [
            {"name": "views"},
            {"name": "estimatedMinutesWatched"},
            {"name": "averageViewDuration"},
            {"name": "subscribersGained"},
            {"name": "likes"},
            {"name": "comments"},
            {"name": "shares"}
        ],
        "rows": [
            [12500, 45000.0, 36.0, 140, 850, 45, 120],
            [8400, 31000.0, 37.0, 95, 520, 30, 85]
        ]
    })

    service.analytics_repo.create_snapshot = AsyncMock(return_value="snap_123")
    service.generate_insights = AsyncMock(return_value=[])

    with patch("backend.app.services.analytics_service.get_youtube_client_for_user", AsyncMock(return_value=mock_yt)):
        result = await service.sync_channel_analytics("u1", "chan_1")

    assert result["status"] == "success"
    assert result["synced_snapshots"] == 2
    assert result["total_views"] == 20900
    assert result["total_watch_hours"] == pytest.approx(1266.67, 0.1)
    assert service.analytics_repo.create_snapshot.call_count == 2
    service.generate_insights.assert_called_once_with("u1", "chan_1")
