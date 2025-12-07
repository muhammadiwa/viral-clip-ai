"""
Property-based tests for Invalid Reset Token Handling.

**Feature: auth-redesign, Property 13: Invalid reset token handling**
**Validates: Requirements 8.5**

Property: For any expired or invalid password reset token, the system SHALL 
display an error message and provide a link to request a new reset.
"""

from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import User, PasswordResetToken
from app.services.password_reset import (
    create_password_reset_token,
    verify_reset_token,
    hash_token,
    generate_reset_token,
)
from app.core.security import hash_password


def create_test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


# Strategy for generating email addresses
email_strategy = st.emails()

# Strategy for generating random tokens
random_token_strategy = st.text(min_size=10, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N')))


@settings(max_examples=100)
@given(random_token=random_token_strategy)
def test_invalid_token_returns_error(random_token: str):
    """
    **Feature: auth-redesign, Property 13: Invalid reset token handling**
    **Validates: Requirements 8.5**
    
    Property: For any random string that is not a valid token, the system
    SHALL return an error indicating the token is invalid.
    """
    db = create_test_db()
    
    try:
        # Verify a random token that doesn't exist
        is_valid, token_record, message = verify_reset_token(db, random_token)
        
        # Should not be valid
        assert not is_valid, "Random token should not be valid"
        assert token_record is None, "Token record should be None for invalid token"
        assert "invalid" in message.lower(), f"Message should indicate invalid token: {message}"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_expired_token_returns_error(email: str):
    """
    **Feature: auth-redesign, Property 13: Invalid reset token handling**
    **Validates: Requirements 8.5**
    
    Property: For any expired token, the system SHALL return an error
    indicating the token has expired.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("testpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create an expired token directly
        raw_token, hashed_token = generate_reset_token()
        expired_token = PasswordResetToken(
            user_id=user.id,
            token=hashed_token,
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            used=False
        )
        db.add(expired_token)
        db.commit()
        
        # Verify the expired token
        is_valid, token_record, message = verify_reset_token(db, raw_token)
        
        # Should not be valid
        assert not is_valid, "Expired token should not be valid"
        assert "expired" in message.lower(), f"Message should indicate token expired: {message}"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_used_token_returns_error(email: str):
    """
    **Feature: auth-redesign, Property 13: Invalid reset token handling**
    **Validates: Requirements 8.5**
    
    Property: For any already-used token, the system SHALL return an error
    indicating the token has been used.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("testpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create a used token directly
        raw_token, hashed_token = generate_reset_token()
        used_token = PasswordResetToken(
            user_id=user.id,
            token=hashed_token,
            expires_at=datetime.utcnow() + timedelta(hours=1),  # Not expired
            used=True  # Already used
        )
        db.add(used_token)
        db.commit()
        
        # Verify the used token
        is_valid, token_record, message = verify_reset_token(db, raw_token)
        
        # Should not be valid
        assert not is_valid, "Used token should not be valid"
        assert "used" in message.lower(), f"Message should indicate token was used: {message}"
        
    finally:
        db.close()


@settings(max_examples=100)
@given(email=email_strategy)
def test_empty_token_returns_error(email: str):
    """
    **Feature: auth-redesign, Property 13: Invalid reset token handling**
    **Validates: Requirements 8.5**
    
    Property: For an empty token string, the system SHALL return an error.
    """
    db = create_test_db()
    
    try:
        # Verify an empty token
        is_valid, token_record, message = verify_reset_token(db, "")
        
        # Should not be valid
        assert not is_valid, "Empty token should not be valid"
        assert token_record is None, "Token record should be None for empty token"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_valid_token_returns_success(email: str):
    """
    **Feature: auth-redesign, Property 13: Invalid reset token handling**
    **Validates: Requirements 8.5**
    
    Property: For any valid (not expired, not used) token, the system
    SHALL return success.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("testpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create a valid token
        raw_token = create_password_reset_token(db, user)
        
        # Verify the valid token
        is_valid, token_record, message = verify_reset_token(db, raw_token)
        
        # Should be valid
        assert is_valid, f"Valid token should be valid: {message}"
        assert token_record is not None, "Token record should be returned for valid token"
        assert "valid" in message.lower(), f"Message should indicate token is valid: {message}"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_token_just_before_expiry_is_valid(email: str):
    """
    **Feature: auth-redesign, Property 13: Invalid reset token handling**
    **Validates: Requirements 8.5**
    
    Property: For any token that is about to expire (but not yet expired),
    the system SHALL still accept it as valid.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("testpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create a token that expires in 1 second
        raw_token, hashed_token = generate_reset_token()
        almost_expired_token = PasswordResetToken(
            user_id=user.id,
            token=hashed_token,
            expires_at=datetime.utcnow() + timedelta(seconds=10),  # Expires in 10 seconds
            used=False
        )
        db.add(almost_expired_token)
        db.commit()
        
        # Verify the almost-expired token
        is_valid, token_record, message = verify_reset_token(db, raw_token)
        
        # Should still be valid
        assert is_valid, f"Almost-expired token should still be valid: {message}"
        
    finally:
        db.close()
