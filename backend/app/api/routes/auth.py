from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import get_settings
from app.models import User
from app.schemas import UserCreate, UserOut, Token
from app.schemas.auth import (
    GoogleAuthRequest, 
    GoogleUserInfo,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyResetTokenResponse,
)
from app.services.rate_limiter import get_rate_limiter
from app.services.password_reset import (
    create_password_reset_token,
    verify_reset_token,
    reset_password,
    send_password_reset_email,
    get_user_by_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Constants for account lockout
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Google OAuth constants
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.post("/register", response_model=UserOut)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user.
    
    Requirements: 9.3
    - WHEN a user submits the registration form THEN the Auth_Page SHALL require 
      completion of a CAPTCHA challenge
    """
    from app.services.captcha import verify_recaptcha, is_captcha_required
    
    # Verify CAPTCHA if required
    if is_captcha_required():
        if not user_in.captcha_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA verification required"
            )
        
        is_valid, error_message = await verify_recaptcha(user_in.captcha_token)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message or "CAPTCHA verification failed"
            )
    
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(user_in.password) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 characters)")
    user = User(
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        credits=100,
        failed_login_attempts=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_generic_auth_error() -> HTTPException:
    """Return a generic authentication error that doesn't reveal user existence."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )


def _get_lockout_error(remaining_seconds: int) -> HTTPException:
    """Return a lockout error with remaining time."""
    remaining_minutes = max(1, remaining_seconds // 60)
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Account temporarily locked. Try again in {remaining_minutes} minute(s)"
    )


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.lower()
    rate_limiter = get_rate_limiter()
    
    # Check if email is rate-limited (in-memory check first)
    is_locked, remaining_seconds = rate_limiter.is_locked(email)
    if is_locked:
        raise _get_lockout_error(remaining_seconds)
    
    # Find user
    user = db.query(User).filter(User.email == email).first()
    
    # Check database-level lockout if user exists
    if user and user.is_locked():
        remaining = user.get_lockout_remaining_seconds()
        raise _get_lockout_error(remaining or LOCKOUT_DURATION_MINUTES * 60)
    
    # Verify credentials - use generic error to prevent user enumeration
    if not user or not verify_password(form_data.password, user.password_hash):
        # Record failed attempt in rate limiter
        is_now_locked, lockout_seconds = rate_limiter.record_failed_attempt(email)
        
        # Also update database if user exists
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            db.commit()
        
        if is_now_locked:
            raise _get_lockout_error(lockout_seconds)
        
        raise _get_generic_auth_error()
    
    # Successful login - reset lockout state
    rate_limiter.record_successful_login(email)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    
    token = create_access_token(user.email)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


async def fetch_google_user_info(access_token: str) -> Optional[GoogleUserInfo]:
    """Fetch user info from Google using the access token."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if response.status_code != 200:
                return None
            data = response.json()
            return GoogleUserInfo(
                id=data.get("id", ""),
                email=data.get("email", ""),
                name=data.get("name"),
                picture=data.get("picture"),
                verified_email=data.get("verified_email", False)
            )
    except Exception:
        return None


def _get_google_auth_error(message: str = "Google authentication failed") -> HTTPException:
    """Return a Google auth error."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message
    )


@router.post("/google", response_model=Token)
async def google_auth(request: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticate user via Google OAuth.
    
    Requirements: 3.2
    - WHEN Google OAuth completes successfully THEN the Auth_System SHALL create or link 
      the user account and issue an access token
    """
    # Fetch user info from Google
    google_user = await fetch_google_user_info(request.access_token)
    
    if not google_user or not google_user.email:
        raise _get_google_auth_error("Failed to retrieve Google user information")
    
    if not google_user.verified_email:
        raise _get_google_auth_error("Google email is not verified")
    
    # Check if user exists by google_id
    user = db.query(User).filter(User.google_id == google_user.id).first()
    
    if user:
        # Existing Google user - update profile info if changed
        if google_user.name and user.name != google_user.name:
            user.name = google_user.name
        if google_user.picture and user.avatar_url != google_user.picture:
            user.avatar_url = google_user.picture
        db.commit()
    else:
        # Check if user exists by email (link existing account)
        user = db.query(User).filter(User.email == google_user.email).first()
        
        if user:
            # Link Google account to existing user
            user.google_id = google_user.id
            if google_user.name and not user.name:
                user.name = google_user.name
            if google_user.picture and not user.avatar_url:
                user.avatar_url = google_user.picture
            db.commit()
        else:
            # Create new user with Google account
            user = User(
                email=google_user.email,
                google_id=google_user.id,
                name=google_user.name,
                avatar_url=google_user.picture,
                password_hash=None,  # No password for Google-only users
                credits=100,
                failed_login_attempts=0,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    
    # Generate access token
    token = create_access_token(user.email)
    return Token(access_token=token)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Request a password reset email.
    
    Requirements: 8.2
    - WHEN a user submits a valid email for password reset THEN the Auth_System 
      SHALL send a password reset email with a secure time-limited token
    
    Note: Always returns success message to prevent email enumeration attacks.
    """
    # Always return success to prevent email enumeration
    success_message = "If an account with that email exists, a password reset link has been sent."
    
    # Find user by email
    user = get_user_by_email(db, request.email)
    
    if user:
        # Only send reset email if user has a password (not Google-only account)
        if user.password_hash is not None:
            # Generate reset token
            reset_token = create_password_reset_token(db, user)
            
            # Send email
            send_password_reset_email(user.email, reset_token)
    
    return ForgotPasswordResponse(message=success_message)


@router.get("/verify-reset-token/{token}", response_model=VerifyResetTokenResponse)
def verify_reset_token_endpoint(token: str, db: Session = Depends(get_db)):
    """
    Verify if a password reset token is valid.
    
    Requirements: 8.5
    - WHEN a password reset token expires or is invalid THEN the Auth_System 
      SHALL display an error message and prompt the user to request a new reset link
    """
    is_valid, _, message = verify_reset_token(db, token)
    
    return VerifyResetTokenResponse(valid=is_valid, message=message)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password_endpoint(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password using a valid token.
    
    Requirements: 8.4
    - WHEN a user submits a new password THEN the Auth_System SHALL update the 
      password and invalidate all existing sessions
    
    Requirements: 8.5
    - WHEN a password reset token expires or is invalid THEN the Auth_System 
      SHALL display an error message
    """
    # Validate password length
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    if len(request.new_password) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too long (max 72 characters)"
        )
    
    # Verify token
    is_valid, token_record, message = verify_reset_token(db, request.token)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Reset password
    reset_password(db, token_record, request.new_password)
    
    return ResetPasswordResponse(message="Password has been reset successfully")
