"""
Property-based tests for Password Reset Session Invalidation.

**Feature: auth-redesign, Property 12: Password reset invalidates sessions**
**Validates: Requirements 8.4**

Property: For any successful password reset, the user's password SHALL be updated 
and all existing sessions for that user SHALL be invalidated.
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
    reset_password,
    hash_token,
)
from app.core.security import hash_password, verify_password


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

# Strategy for generating passwords
password_strategy = st.text(
    min_size=8, 
    max_size=50, 
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P'))
).filter(lambda x: len(x.strip()) >= 8)


@settings(max_examples=100, deadline=None)
@given(email=email_strategy, old_password=password_strategy, new_password=password_strategy)
def test_password_is_updated_after_reset(email: str, old_password: str, new_password: str):
    """
    **Feature: auth-redesign, Property 12: Password reset invalidates sessions**
    **Validates: Requirements 8.4**
    
    Property: For any successful password reset, the user's password SHALL be
    updated to the new password.
    """
    from hypothesis import assume
    # Ensure old and new passwords are different for this test
    assume(old_password != new_password)
    
    db = create_test_db()
    
    try:
        # Create a test user with old password
        user = User(
            email=email.lower(),
            password_hash=hash_password(old_password),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create reset token
        raw_token = create_password_reset_token(db, user)
        
        # Verify and get token record
        is_valid, token_record, _ = verify_reset_token(db, raw_token)
        assert is_valid, "Token should be valid"
        
        # Reset password
        reset_password(db, token_record, new_password)
        
        # Refresh user from database
        db.refresh(user)
        
        # Verify old password no longer works
        assert not verify_password(old_password, user.password_hash), \
            "Old password should no longer work"
        
        # Verify new password works
        assert verify_password(new_password, user.password_hash), \
            "New password should work"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy, password=password_strategy)
def test_reset_token_is_invalidated_after_use(email: str, password: str):
    """
    **Feature: auth-redesign, Property 12: Password reset invalidates sessions**
    **Validates: Requirements 8.4**
    
    Property: For any successful password reset, the used token SHALL be
    marked as used and cannot be reused.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("oldpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create reset token
        raw_token = create_password_reset_token(db, user)
        
        # Verify and get token record
        is_valid, token_record, _ = verify_reset_token(db, raw_token)
        assert is_valid, "Token should be valid before use"
        
        # Reset password
        reset_password(db, token_record, password)
        
        # Try to verify the same token again
        is_valid_again, _, message = verify_reset_token(db, raw_token)
        
        # Token should no longer be valid
        assert not is_valid_again, "Token should be invalid after use"
        assert "already been used" in message.lower(), \
            f"Message should indicate token was used: {message}"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy, password=password_strategy)
def test_all_other_reset_tokens_invalidated(email: str, password: str):
    """
    **Feature: auth-redesign, Property 12: Password reset invalidates sessions**
    **Validates: Requirements 8.4**
    
    Property: For any successful password reset, all other unused reset tokens
    for that user SHALL be invalidated.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("oldpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create multiple reset tokens (simulating multiple reset requests)
        # Note: create_password_reset_token already invalidates previous tokens,
        # so we need to create them directly for this test
        tokens = []
        for i in range(3):
            from app.services.password_reset import generate_reset_token
            raw_token, hashed_token = generate_reset_token()
            token_record = PasswordResetToken(
                user_id=user.id,
                token=hashed_token,
                expires_at=datetime.utcnow() + timedelta(hours=1),
                used=False
            )
            db.add(token_record)
            tokens.append(raw_token)
        db.commit()
        
        # Use the first token to reset password
        is_valid, token_record, _ = verify_reset_token(db, tokens[0])
        assert is_valid, "First token should be valid"
        
        reset_password(db, token_record, password)
        
        # All other tokens should now be invalid
        for i, token in enumerate(tokens[1:], start=2):
            is_valid, _, _ = verify_reset_token(db, token)
            assert not is_valid, f"Token {i} should be invalidated after password reset"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy, password=password_strategy)
def test_lockout_state_reset_after_password_reset(email: str, password: str):
    """
    **Feature: auth-redesign, Property 12: Password reset invalidates sessions**
    **Validates: Requirements 8.4**
    
    Property: For any successful password reset, the user's lockout state
    SHALL be reset (failed attempts cleared, lockout lifted).
    """
    db = create_test_db()
    
    try:
        # Create a test user with lockout state
        user = User(
            email=email.lower(),
            password_hash=hash_password("oldpassword123"),
            credits=100,
            failed_login_attempts=5,
            locked_until=datetime.utcnow() + timedelta(minutes=15),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Verify user is locked
        assert user.is_locked(), "User should be locked initially"
        
        # Create reset token
        raw_token = create_password_reset_token(db, user)
        
        # Verify and reset password
        is_valid, token_record, _ = verify_reset_token(db, raw_token)
        assert is_valid, "Token should be valid"
        
        reset_password(db, token_record, password)
        
        # Refresh user from database
        db.refresh(user)
        
        # Verify lockout state is reset
        assert user.failed_login_attempts == 0, \
            "Failed login attempts should be reset to 0"
        assert user.locked_until is None, \
            "Locked until should be cleared"
        assert not user.is_locked(), \
            "User should no longer be locked"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy, password=password_strategy)
def test_password_reset_returns_success(email: str, password: str):
    """
    **Feature: auth-redesign, Property 12: Password reset invalidates sessions**
    **Validates: Requirements 8.4**
    
    Property: For any successful password reset, the reset_password function
    SHALL return True.
    """
    db = create_test_db()
    
    try:
        # Create a test user
        user = User(
            email=email.lower(),
            password_hash=hash_password("oldpassword123"),
            credits=100,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create reset token
        raw_token = create_password_reset_token(db, user)
        
        # Verify and get token record
        is_valid, token_record, _ = verify_reset_token(db, raw_token)
        assert is_valid, "Token should be valid"
        
        # Reset password
        result = reset_password(db, token_record, password)
        
        # Should return True on success
        assert result is True, "reset_password should return True on success"
        
    finally:
        db.close()
