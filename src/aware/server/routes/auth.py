"""
Authentication routes.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aware.config import settings
from aware.db.engine import get_db
from aware.models import RefreshToken, User
from aware.server.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


# Request/Response schemas
class UserCreate(BaseModel):
    """User registration request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    """User response."""

    id: str
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        return cls(
            id=str(user.id),
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        )


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new user account."""
    # Check if username exists
    result = await db.execute(
        select(User).where(User.username == data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Check if email exists
    result = await db.execute(
        select(User).where(User.email == data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    # Create user
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    await db.flush()

    return UserResponse.from_user(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Login and get access/refresh tokens."""
    # Find user by username
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token, refresh_hash = create_refresh_token()

    # Store refresh token
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
    )
    db.add(db_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh access token using refresh token."""
    # Hash the provided token
    token_hash = hashlib.sha256(data.refresh_token.encode()).hexdigest()

    # Find the refresh token
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check expiration
    now = datetime.now(timezone.utc)
    expires = db_token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if now > expires:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    # Create new tokens
    access_token = create_access_token(db_token.user_id)
    new_refresh, new_hash = create_refresh_token()

    # Revoke old token and create new one
    db_token.revoked = True

    new_expires = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    new_db_token = RefreshToken(
        user_id=db_token.user_id,
        token_hash=new_hash,
        expires_at=new_expires,
    )
    db.add(new_db_token)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Logout and revoke all refresh tokens."""
    # Revoke all user's refresh tokens
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,
        )
    )
    tokens = result.scalars().all()

    for token in tokens:
        token.revoked = True

    return {"detail": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current user info."""
    return UserResponse.from_user(current_user)
