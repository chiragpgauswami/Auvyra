from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str | None = None
    email_verified: bool = False
    created_at: datetime

class UserInDB(BaseModel):
    id: str = Field(alias="_id")
    email: str
    password_hash: str
    name: str
    avatar_url: str | None = None
    email_verified: bool = False
    created_at: datetime
    updated_at: datetime

class OAuthAccount(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    provider: str  # 'google'
    provider_account_id: str
    access_token_encrypted: str
    refresh_token_encrypted: str | None = None
    token_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
