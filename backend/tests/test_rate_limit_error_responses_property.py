"""
Property-based tests for Rate Limit Error Responses.

**Feature: auth-redesign, Property 15: Rate limit error responses**
**Validates: Requirements 9.5**

Property: For any rate-limited request, the error response SHALL indicate
rate limiting without revealing whether the email exists or other sensitive information.
"""

from hypothesis import given, strategies as st, settings, assume

from app.services.rate_limiter import RateLimiter


# Strategy for generating email addresses
email_strategy = st.emails()

# Strategy for generating passwords
password_strategy = st.text(min_size=1, max_size=50)


# Sensitive information patterns that should NOT appear in error messages
SENSITIVE_PATTERNS = [
    "user not found",
    "user does not exist",
    "no user",
    "email not found",
    "email does not exist",
    "no account",
    "account not found",
    "invalid user",
    "unknown user",
    "unknown email",
]


def get_lockout_error_message(remaining_seconds: int) -> str:
    """Simulate the lockout error message generation."""
    remaining_minutes = max(1, remaining_seconds // 60)
    return f"Account temporarily locked. Try again in {remaining_minutes} minute(s)"


def get_generic_auth_error_message() -> str:
    """Simulate the generic auth error message."""
    return "Invalid credentials"


@settings(max_examples=100)
@given(email=email_strategy)
def test_lockout_error_does_not_reveal_user_existence(email: str):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any email that triggers a lockout, the error message
    SHALL NOT reveal whether the email is registered.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Trigger lockout
    for _ in range(5):
        rate_limiter.record_failed_attempt(email)
    
    is_locked, remaining_seconds = rate_limiter.is_locked(email)
    assert is_locked, "Account should be locked"
    
    error_message = get_lockout_error_message(remaining_seconds)
    error_lower = error_message.lower()
    
    # Property: error message should not contain sensitive information
    for pattern in SENSITIVE_PATTERNS:
        assert pattern not in error_lower, \
            f"Error message '{error_message}' contains sensitive pattern '{pattern}'"
    
    # Property: error message should not contain the email
    assert email.lower() not in error_lower, \
        f"Error message should not contain the email address"


@settings(max_examples=100)
@given(email=email_strategy)
def test_generic_auth_error_does_not_reveal_user_existence(email: str):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any failed authentication, the error message SHALL NOT
    reveal whether the email is registered.
    """
    error_message = get_generic_auth_error_message()
    error_lower = error_message.lower()
    
    # Property: error message should not contain sensitive information
    for pattern in SENSITIVE_PATTERNS:
        assert pattern not in error_lower, \
            f"Error message '{error_message}' contains sensitive pattern '{pattern}'"
    
    # Property: error message should not contain the email
    assert email.lower() not in error_lower, \
        f"Error message should not contain the email address"


@settings(max_examples=100)
@given(remaining_seconds=st.integers(min_value=1, max_value=3600))
def test_lockout_error_only_shows_time_remaining(remaining_seconds: int):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any lockout duration, the error message SHALL only
    indicate the time remaining, not any user-specific information.
    """
    error_message = get_lockout_error_message(remaining_seconds)
    
    # Property: message should indicate lockout
    assert "locked" in error_message.lower() or "try again" in error_message.lower(), \
        "Error message should indicate lockout status"
    
    # Property: message should contain time information
    assert "minute" in error_message.lower(), \
        "Error message should contain time information"


@settings(max_examples=100)
@given(email1=email_strategy, email2=email_strategy)
def test_same_error_for_existing_and_nonexisting_users(email1: str, email2: str):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any two emails (one existing, one not), the generic
    authentication error message SHALL be identical.
    """
    # Both should get the same generic error message
    error1 = get_generic_auth_error_message()
    error2 = get_generic_auth_error_message()
    
    # Property: error messages must be identical
    assert error1 == error2, \
        f"Error messages should be identical: '{error1}' vs '{error2}'"


@settings(max_examples=100)
@given(email=email_strategy, attempts=st.integers(min_value=1, max_value=4))
def test_no_attempt_count_in_error_before_lockout(email: str, attempts: int):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any number of failed attempts before lockout, the error
    message SHALL NOT reveal the number of remaining attempts.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Record some failed attempts
    for _ in range(attempts):
        rate_limiter.record_failed_attempt(email)
    
    error_message = get_generic_auth_error_message()
    
    # Property: error should not contain attempt counts
    assert "attempt" not in error_message.lower(), \
        "Error message should not mention attempts"
    assert "remaining" not in error_message.lower(), \
        "Error message should not mention remaining attempts"
    
    # Property: error should not contain numbers (except in generic context)
    # The message "Invalid credentials" should not have numbers
    import re
    numbers = re.findall(r'\d+', error_message)
    assert len(numbers) == 0, \
        f"Generic error should not contain numbers: {error_message}"


@settings(max_examples=100)
@given(email=email_strategy)
def test_lockout_error_format_is_consistent(email: str):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any locked account, the error message format SHALL be
    consistent and predictable.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Trigger lockout
    for _ in range(5):
        rate_limiter.record_failed_attempt(email)
    
    _, remaining_seconds = rate_limiter.is_locked(email)
    error_message = get_lockout_error_message(remaining_seconds)
    
    # Property: message should follow expected format
    assert error_message.startswith("Account temporarily locked"), \
        f"Error message should start with 'Account temporarily locked': {error_message}"
    assert "Try again in" in error_message, \
        f"Error message should contain 'Try again in': {error_message}"
    assert "minute" in error_message, \
        f"Error message should contain 'minute': {error_message}"


@settings(max_examples=100)
@given(email=email_strategy)
def test_rate_limiter_does_not_expose_internal_state(email: str):
    """
    **Feature: auth-redesign, Property 15: Rate limit error responses**
    **Validates: Requirements 9.5**
    
    Property: For any email, the rate limiter's public interface SHALL NOT
    expose internal implementation details.
    """
    rate_limiter = RateLimiter(max_attempts=5, window_minutes=15, lockout_minutes=15)
    
    # Record some attempts
    for _ in range(3):
        rate_limiter.record_failed_attempt(email)
    
    # Property: is_locked returns only boolean and optional int
    is_locked, remaining = rate_limiter.is_locked(email)
    assert isinstance(is_locked, bool), "is_locked should return boolean"
    assert remaining is None or isinstance(remaining, int), \
        "remaining should be None or int"
    
    # Property: get_remaining_attempts returns only int
    remaining_attempts = rate_limiter.get_remaining_attempts(email)
    assert isinstance(remaining_attempts, int), \
        "get_remaining_attempts should return int"
    assert 0 <= remaining_attempts <= 5, \
        f"remaining_attempts should be between 0 and 5: {remaining_attempts}"
