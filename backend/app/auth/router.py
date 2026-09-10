from typing import Optional
from urllib.parse import quote_plus
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from loguru import logger

from backend.app.auth.service import AuthService
from backend.app.auth.dependencies import get_auth_service, get_current_user
from backend.app.models.auth import (
    TokenPair,
    UserRegister,
    UserLogin,
    RefreshRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserResponse
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        return await auth_service.register(data.email, data.password, data.name)
    except ValueError as e:
        code = "EMAIL_EXISTS" if "already registered" in str(e).lower() else "REGISTRATION_FAILED"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": code, "message": str(e)}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Failed to register user"}
        )

@router.post("/login", response_model=TokenPair)
async def login(
    data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        return await auth_service.login(data.login_identifier, data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": str(e)}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Login failed"}
        )

@router.post("/logout")
async def logout(
    data: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    success = await auth_service.logout(data.refresh_token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_SESSION", "message": "Session not found or already revoked"}
        )
    return {"message": "Logged out successfully", "success": True}

@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(
    data: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        return await auth_service.refresh_tokens(data.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": str(e)}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Token refresh failed"}
        )

@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    token = await auth_service.forgot_password(data.email)
    response = {"message": "If an account exists, a reset instruction has been issued."}
    # In development/test mode, expose dev token for automated testing
    if auth_service.settings.APP_ENV in ("development", "test") and token:
        response["reset_token"] = token
        response["dev_reset_token"] = token
    return response

@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        await auth_service.reset_password(data.token, data.new_password)
        return {"message": "Password reset successfully", "success": True}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "RESET_FAILED", "message": str(e)}
        )

from backend.app.youtube.scopes import CANONICAL_OAUTH_SCOPES, get_scope_string

@router.get("/google")
async def google_auth(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    settings = auth_service.settings
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "GOOGLE_AUTH_UNCONFIGURED", "message": "Google OAuth is not configured on this server"}
        )
    scope_param = quote_plus(get_scope_string())
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope_param}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&include_granted_scopes=true"
    )
    accept = request.headers.get("accept", "")
    # If caller specifically wants JSON (e.g. automated test or programmatic API client)
    if "application/json" in accept and "text/html" not in accept:
        return {"url": url}
    # Otherwise browser navigation redirects immediately to Google
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.delete("/google/disconnect")
async def disconnect_google(
    user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Disconnect Google OAuth connection for current user, allowing clean re-authorization."""
    result = await auth_service.oauth_repo.collection.delete_many({"user_id": str(user["_id"]), "provider": "google"})
    return {"success": True, "deleted_count": result.deleted_count, "message": "Google connection disconnected"}

@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    auth_service: AuthService = Depends(get_auth_service)
):
    accept = request.headers.get("accept", "")
    is_browser = "text/html" in accept or "*/*" in accept

    if error:
        logger.warning(f"Google OAuth denied or failed: {error} - {error_description}")
        if is_browser:
            return RedirectResponse(
                url=f"{auth_service.settings.FRONTEND_URL}/login?error={quote_plus(error_description or error)}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "GOOGLE_OAUTH_DENIED", "message": error_description or error}
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_OAUTH_CODE", "message": "Authorization code is required"}
        )

    try:
        token_pair = await auth_service.google_oauth_callback(code)
    except ValueError as e:
        logger.error(f"Failed to exchange Google OAuth code: {e}")
        if is_browser:
            return RedirectResponse(
                url=f"{auth_service.settings.FRONTEND_URL}/login?error={quote_plus(str(e))}",
                status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_EXCHANGE_FAILED", "message": str(e)}
        )

    # For browser navigation, redirect straight to frontend with tokens
    if is_browser:
        redirect_url = (
            f"{auth_service.settings.FRONTEND_URL}/oauth/callback"
            f"?access_token={token_pair.access_token}&refresh_token={token_pair.refresh_token}"
        )
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return token_pair

@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": str(user["_id"]),
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "avatar_url": user.get("avatar_url"),
        "email_verified": user.get("email_verified", False),
        "created_at": user.get("created_at")
    }
