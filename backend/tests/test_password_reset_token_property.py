"""
Property-based tests for Password Reset Token Generation.

**Feature: auth-redesign, Property 11: Password reset token generation**
**Validates: Requirements 8.2**

Property: For any valid email submitted for password reset, the system SHALL 
generate a cryptographically secure token with a time-limited expiration.
"""

from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import User, PasswordResetToken
from app.services.password_reset import (
    generate_reset_token,
    hash_token,
    create_password_reset_token,
    verify_reset_token,
    TOKEN_EXPIRATION_HOURS,
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

# Strategy for generating user names
name_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N', 'P')))


@settings(max_examples=100)
@given(email=email_strategy)
def test_token_generation_produces_unique_tokens(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any email, each call to generate_reset_token SHALL produce
    a unique token.
    """
    tokens = set()
    for _ in range(10):
        raw_token, hashed_token = generate_reset_token()
        # Each token should be unique
        assert raw_token not in tokens, "Generated duplicate raw token"
        tokens.add(raw_token)


@settings(max_examples=100)
@given(email=email_strategy)
def test_token_is_cryptographically_secure_length(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any generated token, the raw token SHALL have sufficient
    length for cryptographic security (at least 32 bytes of entropy).
    """
    raw_token, hashed_token = generate_reset_token()
    
    # Token should be at least 32 characters (base64 encoded 32 bytes)
    assert len(raw_token) >= 32, f"Token too short: {len(raw_token)} chars"
    
    # Hashed token should be SHA-256 (64 hex characters)
    assert len(hashed_token) == 64, f"Hash should be 64 chars, got {len(hashed_token)}"


@settings(max_examples=100)
@given(email=email_strategy)
def test_token_hash_is_deterministic(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any raw token, hashing it multiple times SHALL produce
    the same hash.
    """
    raw_token, _ = generate_reset_token()
    
    hash1 = hash_token(raw_token)
    hash2 = hash_token(raw_token)
    
    assert hash1 == hash2, "Hash should be deterministic"


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_created_token_has_correct_expiration(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any user, a created password reset token SHALL have an
    expiration time of TOKEN_EXPIRATION_HOURS from creation.
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
        
        # Record time before token creation
        before_creation = datetime.utcnow()
        
        # Create token
        raw_token = create_password_reset_token(db, user)
        
        # Record time after token creation
        after_creation = datetime.utcnow()
        
        # Find the token in database
        hashed = hash_token(raw_token)
        token_record = db.query(PasswordResetToken).filter(
            PasswordResetToken.token == hashed
        ).first()
        
        assert token_record is not None, "Token should be stored in database"
        
        # Verify expiration is within expected range
        expected_min = before_creation + timedelta(hours=TOKEN_EXPIRATION_HOURS)
        expected_max = after_creation + timedelta(hours=TOKEN_EXPIRATION_HOURS)
        
        assert token_record.expires_at >= expected_min, "Expiration too early"
        assert token_record.expires_at <= expected_max, "Expiration too late"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_created_token_is_initially_valid(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any newly created token, it SHALL be valid (not used, not expired).
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
        
        # Create token
        raw_token = create_password_reset_token(db, user)
        
        # Verify token is valid
        is_valid, token_record, message = verify_reset_token(db, raw_token)
        
        assert is_valid, f"Newly created token should be valid: {message}"
        assert token_record is not None, "Token record should be returned"
        assert not token_record.used, "Token should not be marked as used"
        assert not token_record.is_expired(), "Token should not be expired"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_new_token_invalidates_previous_tokens(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any user, creating a new reset token SHALL invalidate
    all previous unused tokens for that user.
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
        
        # Create first token
        first_token = create_password_reset_token(db, user)
        
        # Create second token
        second_token = create_password_reset_token(db, user)
        
        # First token should now be invalid (marked as used)
        is_valid_first, _, _ = verify_reset_token(db, first_token)
        assert not is_valid_first, "First token should be invalidated"
        
        # Second token should be valid
        is_valid_second, _, _ = verify_reset_token(db, second_token)
        assert is_valid_second, "Second token should be valid"
        
    finally:
        db.close()


@settings(max_examples=100, deadline=None)
@given(email=email_strategy)
def test_token_is_associated_with_correct_user(email: str):
    """
    **Feature: auth-redesign, Property 11: Password reset token generation**
    **Validates: Requirements 8.2**
    
    Property: For any user, a created token SHALL be associated with that
    specific user.
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
        
        # Create token
        raw_token = create_password_reset_token(db, user)
        
        # Verify token is associated with correct user
        is_valid, token_record, _ = verify_reset_token(db, raw_token)
        
        assert is_valid, "Token should be valid"
        assert token_record.user_id == user.id, "Token should be associated with correct user"
        assert token_record.user.email == user.email, "Token user should match"
        
    finally:
        db.close()
