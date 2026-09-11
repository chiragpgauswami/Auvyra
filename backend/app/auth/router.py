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
    user_id: Optional[str] = None,
    account_hint: Optional[str] = None,
    auth_service: AuthService = Depends(get_auth_service)
):
    settings = auth_service.settings
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "GOOGLE_AUTH_UNCONFIGURED", "message": "Google OAuth is not configured on this server"}
        )

    # Check Authorization header if user_id was not explicitly passed
    current_uid = user_id
    auth_header = request.headers.get("authorization", "")
    if not current_uid and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            payload = auth_service.decode_access_token(token)
            current_uid = payload.get("sub")
        except Exception:
            pass

    state_param = ""
    if current_uid:
        import base64, json
        state_data = json.dumps({"user_id": current_uid})
        state_param = f"&state={quote_plus(base64.urlsafe_b64encode(state_data.encode()).decode())}"

    scope_param = quote_plus(get_scope_string())
    prompt_param = "select_account%20consent" if account_hint else "consent"
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope_param}"
        f"&access_type=offline"
        f"&prompt={prompt_param}"
        f"&include_granted_scopes=true"
        f"{state_param}"
    )
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return {"url": url}
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/google/accounts")
async def get_connected_google_accounts(
    user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """List all connected Google OAuth accounts and their linked YouTube channels."""
    accounts = await auth_service.get_user_oauth_accounts(str(user["_id"]))
    return {"accounts": accounts}

@router.delete("/google/disconnect")
async def disconnect_google(
    account_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Safely disconnect Google OAuth connection without deleting historical channels, videos, or metrics."""
    user_id = str(user["_id"])
    if account_id:
        success = await auth_service.disconnect_oauth_account(user_id, account_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ACCOUNT_NOT_FOUND", "message": "OAuth account not found or does not belong to user"}
            )
        return {"success": True, "message": f"OAuth account {account_id} disconnected successfully"}
    else:
        disconnected_count = await auth_service.disconnect_all_oauth_accounts(user_id)
        return {"success": True, "disconnected_count": disconnected_count, "message": "All Google connections disconnected"}

@router.get("/google/callback")
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
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

    # Extract current_user_id from state if present
    target_user_id = None
    if state:
        try:
            import base64, json
            decoded_state = json.loads(base64.urlsafe_b64decode(state.encode()).decode())
            target_user_id = decoded_state.get("user_id")
        except Exception:
            target_user_id = None

    try:
        token_pair = await auth_service.google_oauth_callback(code, current_user_id=target_user_id)
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
