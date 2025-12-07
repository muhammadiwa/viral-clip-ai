"""Security logging service for authentication events.

Logs suspicious activity patterns for security review.

Requirements: 9.4
- WHEN the Auth_System detects suspicious activity patterns THEN the Auth_System 
  SHALL log the event for security review
"""
import logging
from datetime import datetime
from typing import Optional
from enum import Enum


class SecurityEventType(Enum):
    """Types of security events to log."""
    LOGIN_FAILED = "login_failed"
    LOGIN_SUCCESS = "login_success"
    ACCOUNT_LOCKED = "account_locked"
    RATE_LIMITED = "rate_limited"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_RESET_INVALID_TOKEN = "password_reset_invalid_token"
    GOOGLE_AUTH_SUCCESS = "google_auth_success"
    GOOGLE_AUTH_FAILED = "google_auth_failed"
    REGISTRATION_SUCCESS = "registration_success"
    REGISTRATION_FAILED = "registration_failed"
    CAPTCHA_FAILED = "captcha_failed"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


# Configure security logger
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

# Create handler if not already configured
if not security_logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    security_logger.addHandler(handler)


def log_security_event(
    event_type: SecurityEventType,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[str] = None,
    severity: str = "INFO"
) -> None:
    """Log a security event for review.
    
    Args:
        event_type: Type of security event
        email: Email address involved (masked for privacy)
        ip_address: Client IP address
        user_agent: Client user agent string
        details: Additional details about the event
        severity: Log severity level (INFO, WARNING, ERROR)
    """
    # Mask email for privacy (show first 2 chars and domain)
    masked_email = _mask_email(email) if email else "unknown"
    
    # Build log message
    message_parts = [
        f"event={event_type.value}",
        f"email={masked_email}",
    ]
    
    if ip_address:
        message_parts.append(f"ip={ip_address}")
    
    if user_agent:
        # Truncate user agent to avoid log bloat
        truncated_ua = user_agent[:100] + "..." if len(user_agent) > 100 else user_agent
        message_parts.append(f"user_agent={truncated_ua}")
    
    if details:
        message_parts.append(f"details={details}")
    
    message_parts.append(f"timestamp={datetime.utcnow().isoformat()}")
    
    log_message = " | ".join(message_parts)
    
    # Log at appropriate level
    if severity == "ERROR":
        security_logger.error(log_message)
    elif severity == "WARNING":
        security_logger.warning(log_message)
    else:
        security_logger.info(log_message)


def _mask_email(email: str) -> str:
    """Mask email address for privacy in logs.
    
    Example: john.doe@example.com -> jo***@example.com
    """
    if not email or "@" not in email:
        return "***"
    
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***" if local else "***"
    else:
        masked_local = local[:2] + "***"
    
    return f"{masked_local}@{domain}"


def log_failed_login(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    attempt_count: int = 1
) -> None:
    """Log a failed login attempt."""
    details = f"attempt_count={attempt_count}"
    log_security_event(
        SecurityEventType.LOGIN_FAILED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        severity="WARNING"
    )


def log_account_locked(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    lockout_minutes: int = 15
) -> None:
    """Log an account lockout event."""
    details = f"lockout_duration_minutes={lockout_minutes}"
    log_security_event(
        SecurityEventType.ACCOUNT_LOCKED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        severity="WARNING"
    )


def log_rate_limited(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Log a rate limit event."""
    log_security_event(
        SecurityEventType.RATE_LIMITED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        severity="WARNING"
    )


def log_successful_login(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    auth_method: str = "password"
) -> None:
    """Log a successful login."""
    details = f"auth_method={auth_method}"
    log_security_event(
        SecurityEventType.LOGIN_SUCCESS,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details
    )


def log_password_reset_requested(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Log a password reset request."""
    log_security_event(
        SecurityEventType.PASSWORD_RESET_REQUESTED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_password_reset_completed(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Log a successful password reset."""
    log_security_event(
        SecurityEventType.PASSWORD_RESET_COMPLETED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_invalid_reset_token(
    token_prefix: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    reason: str = "invalid"
) -> None:
    """Log an invalid password reset token attempt."""
    details = f"token_prefix={token_prefix[:8]}... reason={reason}"
    log_security_event(
        SecurityEventType.PASSWORD_RESET_INVALID_TOKEN,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        severity="WARNING"
    )


def log_google_auth_success(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_new_user: bool = False
) -> None:
    """Log a successful Google authentication."""
    details = f"is_new_user={is_new_user}"
    log_security_event(
        SecurityEventType.GOOGLE_AUTH_SUCCESS,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details
    )


def log_google_auth_failed(
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    reason: str = "unknown"
) -> None:
    """Log a failed Google authentication."""
    details = f"reason={reason}"
    log_security_event(
        SecurityEventType.GOOGLE_AUTH_FAILED,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        severity="WARNING"
    )


def log_registration_success(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Log a successful registration."""
    log_security_event(
        SecurityEventType.REGISTRATION_SUCCESS,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_registration_failed(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    reason: str = "unknown"
) -> None:
    """Log a failed registration attempt."""
    details = f"reason={reason}"
    log_security_event(
        SecurityEventType.REGISTRATION_FAILED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        severity="WARNING"
    )


def log_captcha_failed(
    email: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Log a failed CAPTCHA verification."""
    log_security_event(
        SecurityEventType.CAPTCHA_FAILED,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        severity="WARNING"
    )


def log_suspicious_activity(
    description: str,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Log suspicious activity for security review."""
    log_security_event(
        SecurityEventType.SUSPICIOUS_ACTIVITY,
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        details=description,
        severity="ERROR"
    )
