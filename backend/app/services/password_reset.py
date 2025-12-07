"""
Password Reset Service for handling password reset functionality.

Requirements: 8.2, 8.4, 8.5
- WHEN a user submits a valid email for password reset THEN the Auth_System 
  SHALL send a password reset email with a secure time-limited token
- WHEN a user submits a new password THEN the Auth_System SHALL update the 
  password and invalidate all existing sessions
- WHEN a password reset token expires or is invalid THEN the Auth_System 
  SHALL display an error message
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import User, PasswordResetToken
from app.core.security import hash_password
from app.core.config import get_settings


# Token expiration time in hours
TOKEN_EXPIRATION_HOURS = 1


def generate_reset_token() -> Tuple[str, str]:
    """
    Generate a secure password reset token.
    
    Returns:
        Tuple of (raw_token, hashed_token)
        - raw_token: The token to send to the user via email
        - hashed_token: The hashed token to store in the database
    """
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, hashed_token


def hash_token(raw_token: str) -> str:
    """Hash a raw token for database lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_password_reset_token(db: Session, user: User) -> str:
    """
    Create a password reset token for a user.
    
    Args:
        db: Database session
        user: User requesting password reset
        
    Returns:
        The raw token to send to the user
    """
    # Invalidate any existing unused tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False
    ).update({"used": True})
    
    # Generate new token
    raw_token, hashed_token = generate_reset_token()
    
    # Create token record
    token_record = PasswordResetToken(
        user_id=user.id,
        token=hashed_token,
        expires_at=datetime.utcnow() + timedelta(hours=TOKEN_EXPIRATION_HOURS),
        used=False
    )
    db.add(token_record)
    db.commit()
    
    return raw_token


def verify_reset_token(db: Session, raw_token: str) -> Tuple[bool, Optional[PasswordResetToken], str]:
    """
    Verify a password reset token.
    
    Args:
        db: Database session
        raw_token: The raw token from the user
        
    Returns:
        Tuple of (is_valid, token_record, message)
    """
    hashed_token = hash_token(raw_token)
    
    token_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == hashed_token
    ).first()
    
    if not token_record:
        return False, None, "Invalid reset token"
    
    if token_record.used:
        return False, None, "Reset token has already been used"
    
    if token_record.is_expired():
        return False, None, "Reset token has expired"
    
    return True, token_record, "Token is valid"


def reset_password(db: Session, token_record: PasswordResetToken, new_password: str) -> bool:
    """
    Reset a user's password using a valid token.
    
    Args:
        db: Database session
        token_record: The validated token record
        new_password: The new password to set
        
    Returns:
        True if password was reset successfully
    """
    # Get the user
    user = token_record.user
    
    # Update password
    user.password_hash = hash_password(new_password)
    
    # Mark token as used
    token_record.mark_as_used()
    
    # Invalidate all other reset tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != token_record.id,
        PasswordResetToken.used == False
    ).update({"used": True})
    
    # Reset any lockout state
    user.failed_login_attempts = 0
    user.locked_until = None
    
    db.commit()
    
    return True


def send_password_reset_email(email: str, reset_token: str) -> bool:
    """
    Send a password reset email to the user.
    
    In a production environment, this would integrate with an email service
    like SendGrid, AWS SES, or similar.
    
    Args:
        email: User's email address
        reset_token: The raw reset token
        
    Returns:
        True if email was sent successfully
    """
    settings = get_settings()
    
    # Build reset URL
    # In production, this would use the actual frontend URL
    frontend_url = getattr(settings, 'frontend_url', 'http://localhost:5173')
    reset_url = f"{frontend_url}/reset-password?token={reset_token}"
    
    # For now, we'll just log the email (in production, send actual email)
    # This is a placeholder for email service integration
    print(f"[PASSWORD RESET] Sending reset email to {email}")
    print(f"[PASSWORD RESET] Reset URL: {reset_url}")
    
    # In production, you would:
    # 1. Use an email template
    # 2. Send via email service (SendGrid, AWS SES, etc.)
    # 3. Handle delivery failures
    
    return True


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email address (case-insensitive)."""
    return db.query(User).filter(User.email == email.lower()).first()
