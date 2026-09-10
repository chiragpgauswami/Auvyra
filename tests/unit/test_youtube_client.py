import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from backend.app.youtube.client import YouTubeClient, YouTubeAPIError, get_youtube_client_for_user

@pytest.mark.asyncio
async def test_youtube_error_parsing():
    client = YouTubeClient(access_token="test-token")

    # 401
    resp_401 = httpx.Response(status_code=401, json={"error": {"message": "Invalid Credentials"}})
    err_401 = client._parse_error(resp_401)
    assert err_401.status_code == 401
    assert err_401.error_code == "YOUTUBE_AUTH_EXPIRED"

    # 403 Insufficient Scopes
    resp_403_scope = httpx.Response(
        status_code=403,
        json={"error": {"message": "Request had insufficient authentication scopes.", "errors": [{"reason": "insufficientPermissions"}]}}
    )
    err_403_scope = client._parse_error(resp_403_scope)
    assert err_403_scope.error_code == "YOUTUBE_INSUFFICIENT_SCOPES"

    # 403 Quota
    resp_403_quota = httpx.Response(
        status_code=403,
        json={"error": {"message": "Daily limit exceeded", "errors": [{"reason": "quotaExceeded"}]}}
    )
    err_403_quota = client._parse_error(resp_403_quota)
    assert err_403_quota.error_code == "YOUTUBE_QUOTA_EXCEEDED"

    # 404 Not Found
    resp_404 = httpx.Response(status_code=404, json={"error": {"message": "Not found"}})
    err_404 = client._parse_error(resp_404)
    assert err_404.error_code == "YOUTUBE_NOT_FOUND"

    # 500 Server error
    resp_500 = httpx.Response(status_code=500, text="Internal Server Error")
    err_500 = client._parse_error(resp_500)
    assert err_500.error_code == "YOUTUBE_SERVER_ERROR"
    assert err_500.retryable is True

@pytest.mark.asyncio
async def test_get_my_channel_parses_statistics():
    client = YouTubeClient(access_token="valid-token")

    mock_channel_response = {
        "items": [{
            "id": "UC_TEST_CHANNEL_123",
            "snippet": {
                "title": "Auvyra Tech",
                "customUrl": "@auvyratech",
                "description": "Tech videos automated by Auvyra",
                "thumbnails": {
                    "high": {"url": "https://example.com/thumb_high.jpg"}
                }
            },
            "statistics": {
                "subscriberCount": "12500",
                "videoCount": "42",
                "viewCount": "980000"
            }
        }]
    }

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_req.return_value = httpx.Response(status_code=200, json=mock_channel_response)
        channel = await client.get_my_channel()

        assert channel["youtube_channel_id"] == "UC_TEST_CHANNEL_123"
        assert channel["name"] == "Auvyra Tech"
        assert channel["handle"] == "@auvyratech"
        assert channel["subscriber_count"] == 12500
        assert channel["video_count"] == 42
        assert channel["view_count"] == 980000
        assert channel["thumbnail_url"] == "https://example.com/thumb_high.jpg"

@pytest.mark.asyncio
async def test_auto_token_refresh_on_401():
    refreshed_tokens = []

    async def callback(new_token, expires_in):
        refreshed_tokens.append(new_token)

    client = YouTubeClient(
        access_token="expired-token",
        refresh_token="valid-refresh-token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        token_refreshed_callback=callback
    )

    mock_refresh_response = {
        "access_token": "brand-new-access-token",
        "expires_in": 3600,
        "token_type": "Bearer"
    }

    mock_channel_response = {
        "items": [{
            "id": "UC_REFRESHED",
            "snippet": {"title": "Refreshed Channel", "thumbnails": {}},
            "statistics": {"subscriberCount": "100", "videoCount": "5", "viewCount": "500"}
        }]
    }

    with patch("httpx.AsyncClient.request") as mock_req, patch("httpx.AsyncClient.post") as mock_post:
        mock_req.side_effect = [
            httpx.Response(status_code=401, json={"error": {"message": "Invalid Credentials"}}),
            httpx.Response(status_code=200, json=mock_channel_response)
        ]
        mock_post.return_value = httpx.Response(status_code=200, json=mock_refresh_response)

        ch = await client.get_my_channel()

        assert ch["youtube_channel_id"] == "UC_REFRESHED"
        assert client.access_token == "brand-new-access-token"
        assert refreshed_tokens == ["brand-new-access-token"]

