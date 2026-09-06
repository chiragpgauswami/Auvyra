from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.app.config import get_settings, Settings
from backend.app.database import get_db
from backend.app.auth.service import AuthService

security = HTTPBearer()

async def get_auth_service(db = Depends(get_db), settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(db, settings)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> dict:
    """Extract and verify the authenticated user from JWT.
    NEVER trust user_id from the frontend."""
    token = credentials.credentials
    try:
        user = await auth_service.get_current_user(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def require_auth(user: dict = Depends(get_current_user)) -> dict:
    """Alias for get_current_user with clearer intent."""
    return user
