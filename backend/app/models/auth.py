"""Authentication and Token Models for Auvyra."""

from pydantic import BaseModel, EmailStr, Field
from backend.app.models.user import TokenPair, UserCreate, UserResponse, UserInDB, OAuthAccount

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")
    name: str = Field(min_length=1, max_length=100)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

__all__ = [
    "TokenPair",
    "UserCreate",
    "UserResponse",
    "UserInDB",
    "OAuthAccount",
    "UserRegister",
    "UserLogin",
    "RefreshRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
]
