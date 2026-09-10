import os
import tempfile
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException

from backend.app.api.videos import _validate_safe_video_path, _resolve_and_authorize_video
from backend.app.models.auth import UserResponse
from backend.app.config import Settings
from backend.app.auth.service import AuthService


def test_path_traversal_prevention_on_relative_and_absolute_attempts():
    """Verify path traversal attacks targeting sensitive system or outside files are blocked."""
    with tempfile.TemporaryDirectory() as allowed_dir:
        allowed_dirs = [allowed_dir]

        # 1. Obvious relative traversal
        with pytest.raises(HTTPException) as exc1:
            _validate_safe_video_path("../../etc/passwd", allowed_dirs)
        assert exc1.value.status_code == 403
        assert exc1.value.detail["code"] == "PATH_TRAVERSAL_DETECTED"

        # 2. Absolute path traversal targeting outside directory
        with pytest.raises(HTTPException) as exc2:
            _validate_safe_video_path("/etc/passwd", allowed_dirs)
        assert exc2.value.status_code == 403
        assert exc2.value.detail["code"] == "PATH_TRAVERSAL_DETECTED"

        # 3. Legitimate file inside allowed directory passes
        legit_file = os.path.join(allowed_dir, "video.mp4")
        with open(legit_file, "wb") as f:
            f.write(b"dummy mp4 data")

        safe_result = _validate_safe_video_path(legit_file, allowed_dirs)
        assert safe_result == os.path.realpath(legit_file)


@pytest.mark.asyncio
async def test_video_authorization_boundaries():
    """Verify unauthorized or cross-tenant video access is strictly forbidden."""
    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "user_a_video.mp4")
        with open(video_path, "wb") as f:
            f.write(b"video data")

        mock_service = MagicMock()
        mock_service.storage.root_dir = temp_dir
        mock_service.video_repo = MagicMock()
        mock_service.job_repo = MagicMock()

        video_doc = {
            "_id": "video_123",
            "user_id": "user_owner_a",
            "title": "Private User A Video",
            "file_path": video_path
        }
        mock_service.video_repo.find_by_id = AsyncMock(return_value=video_doc)

        mock_auth_service = MagicMock()

        # 1. Unauthenticated request (no token) -> 401
        req_unauth = MagicMock()
        req_unauth.headers = {}
        with pytest.raises(HTTPException) as exc_unauth:
            await _resolve_and_authorize_video("video_123", req_unauth, None, mock_service, mock_auth_service)
        assert exc_unauth.value.status_code == 401
        assert exc_unauth.value.detail["code"] == "UNAUTHORIZED"

        # 2. Invalid token -> 401
        mock_auth_service.get_current_user = AsyncMock(side_effect=ValueError("Invalid JWT"))
        with pytest.raises(HTTPException) as exc_invalid:
            await _resolve_and_authorize_video("video_123", req_unauth, "bad_token", mock_service, mock_auth_service)
        assert exc_invalid.value.status_code == 401
        assert exc_invalid.value.detail["code"] == "INVALID_TOKEN"

        # 3. Cross-tenant request (User B attempts to access User A's video) -> 403
        mock_auth_service.get_current_user = AsyncMock(return_value={"_id": "user_intruder_b", "email": "b@example.com"})
        with pytest.raises(HTTPException) as exc_forbidden:
            await _resolve_and_authorize_video("video_123", req_unauth, "token_b", mock_service, mock_auth_service)
        assert exc_forbidden.value.status_code == 403
        assert exc_forbidden.value.detail["code"] == "FORBIDDEN"

        # 4. Valid owner request (User A accessing User A's video) -> Allowed
        mock_auth_service.get_current_user = AsyncMock(return_value={"_id": "user_owner_a", "email": "a@example.com"})
        ret_video, ret_path = await _resolve_and_authorize_video("video_123", req_unauth, "token_a", mock_service, mock_auth_service)
        assert ret_video["_id"] == "video_123"
        assert ret_path == os.path.realpath(video_path)


def test_user_response_model_excludes_sensitive_credentials():
    """Verify that UserResponse schema never leaks passwords, password hashes, or session tokens."""
    data = {
        "id": "6a9da1ca3b0d15115110a63f",
        "email": "creator@auvyra.test",
        "name": "Alex Creator",
        "avatar_url": "https://auvyra.test/avatar.png",
        "email_verified": True,
        "created_at": "2026-09-10T12:00:00Z",
        # Extra sensitive fields that should NEVER be accepted or leaked
        "password_hash": "$2b$12$eX4mpL3hAsHnOtL34k3d",
        "refresh_token": "secret_refresh_token_string",
        "encryption_key": "some_fernet_key"
    }
    user_res = UserResponse.model_validate(data)
    dumped = user_res.model_dump()

    assert "password_hash" not in dumped
    assert "refresh_token" not in dumped
    assert "encryption_key" not in dumped
    assert dumped["email"] == "creator@auvyra.test"


def test_fernet_token_encryption_at_rest():
    """Verify that OAuth refresh and access tokens are strictly encrypted before MongoDB persistence."""
    settings = Settings(
        ENCRYPTION_KEY="test_key_placeholder",
        JWT_SECRET="test_jwt_secret"
    )
    # Generate valid key
    fernet = settings.get_fernet()
    auth_service = AuthService(db=MagicMock(), settings=settings)

    raw_token = "ya29.a0ARrdaM-sensitive-google-oauth-token-value"
    encrypted = auth_service.encrypt_token(raw_token)

    assert encrypted != raw_token
    assert raw_token not in encrypted
    decrypted = auth_service.decrypt_token(encrypted)
    assert decrypted == raw_token

