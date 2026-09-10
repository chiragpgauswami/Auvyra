"""Authentication and Token Models for Auvyra."""

from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, model_validator
from backend.app.models.user import TokenPair, UserCreate, UserResponse, UserInDB, OAuthAccount

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")
    name: str = Field(min_length=1, max_length=100)

class UserLogin(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str

    @model_validator(mode="before")
    @classmethod
    def resolve_email_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("email") and data.get("username"):
                data["email"] = data["username"]
        return data

    @property
    def login_identifier(self) -> str:
        return str(self.email or self.username or "")

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

