import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
from jose import JWTError, jwt
from cryptography.fernet import Fernet
import httpx
from bson import ObjectId
from loguru import logger

from backend.app.config import Settings
from backend.app.models.user import TokenPair
from backend.app.repositories.users import UserRepository, OAuthAccountRepository, SessionRepository
from backend.app.repositories.channels import ChannelRepository

class AuthService:
    def __init__(self, db, settings: Settings):
        self.db = db
        self.fernet = settings.get_fernet()
        self.user_repo = UserRepository(db)
        self.oauth_repo = OAuthAccountRepository(db)
        self.session_repo = SessionRepository(db)
        self.channel_repo = ChannelRepository(db)
        self.settings = settings
    
    # ----------------------------------------------------------------------
    # Password hashing
    # ----------------------------------------------------------------------
    def hash_password(self, password: str) -> str:
        pw_bytes = password.encode("utf-8")[:72]
        return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")
        
    def verify_password(self, plain: str, hashed: str) -> bool:
        if not hashed:
            return False
        pw_bytes = plain.encode("utf-8")[:72]
        try:
            return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
        except Exception:
            return False
    
    # ----------------------------------------------------------------------
    # Token management
    # ----------------------------------------------------------------------
    def create_access_token(self, user_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "exp": expire,
            "sub": str(user_id),
            "type": "access"
        }
        encoded_jwt = jwt.encode(to_encode, self.settings.JWT_SECRET, algorithm=self.settings.JWT_ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self) -> str:
        return secrets.token_urlsafe(48)

    def decode_access_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self.settings.JWT_SECRET, algorithms=[self.settings.JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise ValueError("Token is not an access token")
            return payload
        except JWTError as e:
            raise ValueError(f"Invalid access token: {e}")

    def hash_refresh_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()
    
    # ----------------------------------------------------------------------
    # OAuth token encryption
    # ----------------------------------------------------------------------
    def encrypt_token(self, token: str) -> str:
        if not token:
            return ""
        return self.fernet.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted: str) -> str:
        if not encrypted:
            return ""
        return self.fernet.decrypt(encrypted.encode()).decode()
    
    # ----------------------------------------------------------------------
    # Core auth flows
    # ----------------------------------------------------------------------
    async def register(self, email: str, password: str, name: str) -> TokenPair:
        existing = await self.user_repo.find_by_email(email)
        if existing:
            raise ValueError("Email already registered")
            
        password_hash = self.hash_password(password)
        now = datetime.now(timezone.utc)
        user_doc = {
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "name": name.strip(),
            "avatar_url": None,
            "email_verified": False,
            "created_at": now,
            "updated_at": now,
            "is_active": True
        }
        
        user_id = await self.user_repo.create_user(user_doc)
        
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token()
        hashed_rt = self.hash_refresh_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await self.session_repo.create_session(user_id, hashed_rt, expires_at)
        
        return TokenPair(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    
    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.user_repo.find_by_email(email.lower().strip())
        if not user or not self.verify_password(password, user.get("password_hash", "")):
            raise ValueError("Incorrect email or password")
            
        user_id = str(user["_id"])
        
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token()
        hashed_rt = self.hash_refresh_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await self.session_repo.create_session(user_id, hashed_rt, expires_at)
        
        return TokenPair(access_token=access_token, refresh_token=refresh_token, token_type="bearer")
    
    async def logout(self, refresh_token: str) -> bool:
        hashed_rt = self.hash_refresh_token(refresh_token)
        session = await self.session_repo.find_valid_session(hashed_rt)
        if session:
            await self.session_repo.revoke_session(str(session["_id"]))
            return True
        return False
    
    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        hashed_rt = self.hash_refresh_token(refresh_token)
        session = await self.session_repo.find_valid_session(hashed_rt)
        
        if not session:
            raise ValueError("Invalid or expired refresh token")
            
        user_id = session["user_id"]
        
        # Revoke old session (Rotation)
        await self.session_repo.revoke_session(str(session["_id"]))
        
        # Verify user still exists
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError("User no longer exists")
        
        # Create new session
        new_access_token = self.create_access_token(user_id)
        new_refresh_token = self.create_refresh_token()
        new_hashed_rt = self.hash_refresh_token(new_refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        await self.session_repo.create_session(user_id, new_hashed_rt, expires_at)
        
        return TokenPair(access_token=new_access_token, refresh_token=new_refresh_token, token_type="bearer")
    
    async def forgot_password(self, email: str) -> Optional[str]:
        user = await self.user_repo.find_by_email(email.lower().strip())
        if not user:
            return None
            
        expire = datetime.now(timezone.utc) + timedelta(hours=1)
        to_encode = {"exp": expire, "sub": str(user["_id"]), "type": "reset"}
        reset_token = jwt.encode(to_encode, self.settings.JWT_SECRET, algorithm=self.settings.JWT_ALGORITHM)
        
        return reset_token
    
    async def reset_password(self, reset_token: str, new_password: str) -> bool:
        try:
            payload = jwt.decode(reset_token, self.settings.JWT_SECRET, algorithms=[self.settings.JWT_ALGORITHM])
            if payload.get("type") != "reset":
                raise ValueError("Invalid token type")
            user_id = payload.get("sub")
        except JWTError:
            raise ValueError("Invalid or expired reset token")
            
        password_hash = self.hash_password(new_password)
        updated = await self.user_repo.update_password(user_id, password_hash)
        if not updated:
            raise ValueError("User not found or password update failed")
        
        # Invalidate all active sessions for security
        await self.session_repo.revoke_all_user_sessions(user_id)
        return True
    
    async def google_oauth_callback(self, code: str) -> TokenPair:
        if not self.settings.GOOGLE_CLIENT_ID or not self.settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("Google OAuth is not configured on this server")

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.settings.GOOGLE_CLIENT_ID,
                    "client_secret": self.settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.settings.GOOGLE_REDIRECT_URI
                }
            )
            if token_response.status_code != 200:
                raise ValueError(f"Failed to exchange code for Google tokens: {token_response.text}")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            google_refresh_token = tokens.get("refresh_token")
            expires_in = tokens.get("expires_in")
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in else None
            
            # Extract and audit granted scopes
            raw_scope = tokens.get("scope", "")
            granted_scopes = [s.strip() for s in raw_scope.split(" ") if s.strip()]
            logger.info(f"OAuth token acquired. Granted scopes ({len(granted_scopes)}):")
            for s in granted_scopes:
                logger.info(f"  - {s}")

            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if user_info_response.status_code != 200:
                raise ValueError("Failed to fetch Google user info")
                
            user_info = user_info_response.json()
            email = user_info.get("email")
            name = user_info.get("name") or "YouTube Creator"
            google_id = user_info.get("id")
            
        user = await self.user_repo.find_by_email(email)
        now = datetime.now(timezone.utc)
        if not user:
            user_doc = {
                "email": email.lower().strip(),
                "name": name,
                "created_at": now,
                "updated_at": now,
                "email_verified": True,
                "password_hash": ""
            }
            user_id = await self.user_repo.create_user(user_doc)
        else:
            user_id = str(user["_id"])
            
        from backend.app.youtube.scopes import verify_granted_scopes
        scope_audit = verify_granted_scopes(granted_scopes)
        if not scope_audit["valid"]:
            logger.warning(
                f"OAuth credentials for user {user_id} missing required YouTube scopes: "
                f"{scope_audit['missing_scopes']}. Reauthorization required for full features."
            )

        # Encrypt sensitive OAuth tokens before storing into MongoDB
        oauth_data = {
            "user_id": user_id,
            "provider": "google",
            "provider_account_id": google_id,
            "access_token_encrypted": self.encrypt_token(access_token),
            "refresh_token_encrypted": self.encrypt_token(google_refresh_token) if google_refresh_token else None,
            "token_expires_at": token_expires_at,
            "granted_scopes": granted_scopes,
            "scope_valid": scope_audit["valid"],
            "missing_scopes": scope_audit["missing_scopes"],
            "updated_at": now
        }
        await self.oauth_repo.upsert(user_id, "google", oauth_data)

        # Auto-discover and link YouTube channel for this user
        has_read_scope = (
            "https://www.googleapis.com/auth/youtube.readonly" in granted_scopes
            or "https://www.googleapis.com/auth/youtube" in granted_scopes
        )
        if has_read_scope:
            try:
                from backend.app.youtube.client import YouTubeClient, YouTubeAPIError
                yt_client = YouTubeClient(access_token=access_token)
                yt_info = await yt_client.get_my_channel()
                yt_id = yt_info.get("youtube_channel_id") or yt_info.get("id")
                if yt_id:
                    existing_ch = await self.channel_repo.find_by_youtube_id(yt_id)
                    if not existing_ch:
                        await self.channel_repo.insert_one({
                            "user_id": user_id,
                            "name": yt_info.get("name") or yt_info.get("title") or "YouTube Channel",
                            "description": yt_info.get("description") or "",
                            "youtube_channel_id": yt_id,
                            "handle": yt_info.get("handle") or yt_info.get("customUrl"),
                            "thumbnail_url": yt_info.get("thumbnail_url"),
                            "subscriber_count": yt_info.get("subscriber_count", 0),
                            "video_count": yt_info.get("video_count", 0),
                            "view_count": yt_info.get("view_count", 0),
                            "status": "connected",
                            "autopilot_enabled": False,
                            "approval_required": True,
                            "created_at": now,
                            "updated_at": now
                        })
                        logger.info(f"Auto-created and linked YouTube channel '{yt_info.get('name')}' ({yt_id}) for user {user_id}")
                    else:
                        await self.channel_repo.update_one(str(existing_ch["_id"]), {
                            "user_id": user_id,
                            "status": "connected",
                            "name": yt_info.get("name") or yt_info.get("title") or existing_ch.get("name"),
                            "handle": yt_info.get("handle") or yt_info.get("customUrl") or existing_ch.get("handle"),
                            "thumbnail_url": yt_info.get("thumbnail_url") or existing_ch.get("thumbnail_url"),
                            "subscriber_count": yt_info.get("subscriber_count", existing_ch.get("subscriber_count", 0)),
                            "video_count": yt_info.get("video_count", existing_ch.get("video_count", 0)),
                            "view_count": yt_info.get("view_count", existing_ch.get("view_count", 0)),
                            "updated_at": now
                        })
                        logger.info(f"Re-linked YouTube channel '{yt_info.get('name')}' ({yt_id}) for user {user_id}")
            except YouTubeAPIError as yt_err:
                if yt_err.error_code == "NO_CHANNEL":
                    logger.info(f"Google account for user {user_id} does not have an active YouTube channel.")
                else:
                    logger.error(f"YouTube API error during channel auto-linking: {yt_err.message} (code: {yt_err.error_code})")
            except Exception as yt_err:
                logger.error(f"Unexpected error linking YouTube channel during OAuth: {yt_err}")
        else:
            logger.warning(
                f"Skipping YouTube channel lookup: granted_scopes lacks 'https://www.googleapis.com/auth/youtube.readonly'. "
                f"User must re-authenticate with prompt=consent to grant read access."
            )
        
        # Create session
        new_access_token = self.create_access_token(user_id)
        new_refresh_token = self.create_refresh_token()
        hashed_rt = self.hash_refresh_token(new_refresh_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.session_repo.create_session(user_id, hashed_rt, expires_at)
        
        return TokenPair(access_token=new_access_token, refresh_token=new_refresh_token, token_type="bearer")

    async def get_current_user(self, token: str) -> dict:
        payload = self.decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token subject missing")
            
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return user
