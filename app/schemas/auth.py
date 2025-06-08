# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserSignUp(BaseModel):
    """Схема для регистрации пользователя"""
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: Optional[str] = Field(default=None, max_length=255)


class UserSignIn(BaseModel):
    """Схема для входа пользователя"""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Схема ответа с токеном"""
    access_token: str
    token_type: str = "bearer"
    user: Optional[dict] = None


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя"""
    id: int
    email: str
    name: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True
