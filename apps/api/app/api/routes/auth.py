from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...core.config import get_settings
from ...core.security import create_access_token
from ...domain.auth import TokenRequest, TokenResponse
from ...domain.users import User, UserResponse
from ...repositories.users import UsersRepository
from ..dependencies import get_current_user, get_users_repository

router = APIRouter(tags=["auth"])


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(
    payload: TokenRequest,
    users_repo: UsersRepository = Depends(get_users_repository),
) -> TokenResponse:
    user = await users_repo.verify_credentials(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    updated_user = await users_repo.touch_last_login(user.id)
    if updated_user is not None:
        user = updated_user
    settings = get_settings()
    access_token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=user,
    )


@router.get("/auth/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(data=current_user)
