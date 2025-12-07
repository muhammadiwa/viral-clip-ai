"""
Property-based tests for Account Lockout functionality.

**Feature: auth-redesign, Property 14: Account lockout after failed attempts**
**Validates: Requirements 9.1, 9.2**

Property: For any user who fails login 5 times within 15 minutes, the account
SHALL be locked for 15 minutes and display a message indicating the lockout duration.
"""

from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume

from app.services.rate_limiter import RateLimiter, reset_rate_limiter


# Strategy for generating email addresses
email_strategy = st.emails()

# Strategy for number of failed attempts
attempts_strategy = st.integers(min_value=1, max_value=20)


@settings(max_examples=100)
@given(email=email_strategy)
def test_account_locks_after_max_failed_attempts(email: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any email, after exactly 5 failed login attempts within the
    time window, the account SHALL be locked.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Record 4 failed attempts - should not be locked yet
    for i in range(4):
        is_locked, _ = rate_limiter.record_failed_attempt(email)
        assert not is_locked, f"Account locked after only {i+1} attempts"
    
    # 5th attempt should trigger lockout
    is_locked, lockout_seconds = rate_limiter.record_failed_attempt(email)
    
    # Property: account must be locked after 5 failed attempts
    assert is_locked, "Account should be locked after 5 failed attempts"
    assert lockout_seconds is not None, "Lockout seconds should be provided"
    assert lockout_seconds > 0, "Lockout duration should be positive"


@settings(max_examples=100)
@given(email=email_strategy, num_attempts=st.integers(min_value=1, max_value=4))
def test_account_not_locked_before_max_attempts(email: str, num_attempts: int):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any email and any number of failed attempts less than 5,
    the account SHALL NOT be locked.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    for i in range(num_attempts):
        is_locked, _ = rate_limiter.record_failed_attempt(email)
    
    # Property: account should not be locked with fewer than max attempts
    is_locked, _ = rate_limiter.is_locked(email)
    assert not is_locked, f"Account should not be locked after only {num_attempts} attempts"


@settings(max_examples=100)
@given(email=email_strategy)
def test_lockout_duration_is_correct(email: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any locked account, the lockout duration SHALL be 15 minutes
    (900 seconds).
    """
    lockout_minutes = 15
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=lockout_minutes)
    
    # Trigger lockout
    for _ in range(5):
        rate_limiter.record_failed_attempt(email)
    
    is_locked, remaining_seconds = rate_limiter.is_locked(email)
    
    # Property: lockout duration should be approximately 15 minutes
    assert is_locked, "Account should be locked"
    assert remaining_seconds is not None, "Remaining seconds should be provided"
    # Allow small tolerance for execution time
    expected_seconds = lockout_minutes * 60
    assert remaining_seconds <= expected_seconds, \
        f"Remaining seconds {remaining_seconds} exceeds expected {expected_seconds}"
    assert remaining_seconds > expected_seconds - 5, \
        f"Remaining seconds {remaining_seconds} is too low"


@settings(max_examples=100)
@given(email=email_strategy)
def test_successful_login_resets_lockout_state(email: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any email, a successful login SHALL reset the failed
    attempt counter and lockout state.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Record some failed attempts (but not enough to lock)
    for _ in range(3):
        rate_limiter.record_failed_attempt(email)
    
    # Simulate successful login
    rate_limiter.record_successful_login(email)
    
    # Property: after successful login, attempts should be reset
    remaining = rate_limiter.get_remaining_attempts(email)
    assert remaining == 5, f"Expected 5 remaining attempts after reset, got {remaining}"


@settings(max_examples=100)
@given(email=email_strategy)
def test_locked_account_returns_remaining_time(email: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any locked account, checking lock status SHALL return
    the remaining lockout time in seconds.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Trigger lockout
    for _ in range(5):
        rate_limiter.record_failed_attempt(email)
    
    is_locked, remaining_seconds = rate_limiter.is_locked(email)
    
    # Property: locked account should provide remaining time
    assert is_locked, "Account should be locked"
    assert remaining_seconds is not None, "Remaining seconds must be provided for locked account"
    assert isinstance(remaining_seconds, int), "Remaining seconds should be an integer"
    assert remaining_seconds > 0, "Remaining seconds should be positive"


@settings(max_examples=100)
@given(email=email_strategy)
def test_remaining_attempts_decreases_with_failures(email: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any email, each failed attempt SHALL decrease the
    remaining attempts by 1.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    for i in range(4):
        expected_remaining = 5 - i
        actual_remaining = rate_limiter.get_remaining_attempts(email)
        assert actual_remaining == expected_remaining, \
            f"Expected {expected_remaining} remaining, got {actual_remaining}"
        
        rate_limiter.record_failed_attempt(email)
    
    # After 4 failures, should have 1 remaining
    assert rate_limiter.get_remaining_attempts(email) == 1


@settings(max_examples=100)
@given(email1=email_strategy, email2=email_strategy)
def test_lockout_is_per_email(email1: str, email2: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any two different emails, lockout state SHALL be
    tracked independently.
    """
    assume(email1.lower() != email2.lower())
    
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Lock email1
    for _ in range(5):
        rate_limiter.record_failed_attempt(email1)
    
    # email1 should be locked
    is_locked1, _ = rate_limiter.is_locked(email1)
    assert is_locked1, "email1 should be locked"
    
    # email2 should NOT be locked
    is_locked2, _ = rate_limiter.is_locked(email2)
    assert not is_locked2, "email2 should not be locked"
    
    # email2 should have full attempts available
    remaining = rate_limiter.get_remaining_attempts(email2)
    assert remaining == 5, f"email2 should have 5 attempts, got {remaining}"


@settings(max_examples=100)
@given(email=email_strategy)
def test_email_case_insensitivity(email: str):
    """
    **Feature: auth-redesign, Property 14: Account lockout after failed attempts**
    **Validates: Requirements 9.1, 9.2**
    
    Property: For any email, lockout tracking SHALL be case-insensitive.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Record failures with lowercase
    for _ in range(3):
        rate_limiter.record_failed_attempt(email.lower())
    
    # Check remaining with uppercase
    remaining = rate_limiter.get_remaining_attempts(email.upper())
    
    # Property: case should not matter
    assert remaining == 2, f"Expected 2 remaining attempts, got {remaining}"
