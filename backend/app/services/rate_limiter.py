"""Rate limiter service for authentication endpoints.

Implements sliding window rate limiting to track failed login attempts per email.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
import threading


@dataclass
class RateLimitEntry:
    """Tracks rate limit data for a single email."""
    attempts: int = 0
    window_start: datetime = field(default_factory=datetime.utcnow)
    locked_until: Optional[datetime] = None


class RateLimiter:
    """In-memory rate limiter with sliding window algorithm.
    
    Tracks failed login attempts per email and implements account lockout
    after exceeding the maximum attempts within the time window.
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        window_minutes: int = 15,
        lockout_minutes: int = 15
    ):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.lockout_minutes = lockout_minutes
        self._entries: Dict[str, RateLimitEntry] = {}
        self._lock = threading.Lock()
    
    def _get_entry(self, email: str) -> RateLimitEntry:
        """Get or create rate limit entry for email."""
        email_lower = email.lower()
        if email_lower not in self._entries:
            self._entries[email_lower] = RateLimitEntry()
        return self._entries[email_lower]
    
    def _is_window_expired(self, entry: RateLimitEntry) -> bool:
        """Check if the rate limit window has expired."""
        window_end = entry.window_start + timedelta(minutes=self.window_minutes)
        return datetime.utcnow() > window_end
    
    def is_locked(self, email: str) -> Tuple[bool, Optional[int]]:
        """Check if an email is currently locked out.
        
        Returns:
            Tuple of (is_locked, remaining_seconds)
        """
        with self._lock:
            entry = self._get_entry(email)
            
            if entry.locked_until is None:
                return False, None
            
            now = datetime.utcnow()
            if now >= entry.locked_until:
                # Lockout expired, reset
                entry.locked_until = None
                entry.attempts = 0
                entry.window_start = now
                return False, None
            
            remaining = int((entry.locked_until - now).total_seconds())
            return True, remaining
    
    def record_failed_attempt(self, email: str) -> Tuple[bool, Optional[int]]:
        """Record a failed login attempt.
        
        Returns:
            Tuple of (is_now_locked, lockout_seconds)
        """
        with self._lock:
            entry = self._get_entry(email)
            now = datetime.utcnow()
            
            # If already locked, return lockout info
            if entry.locked_until and now < entry.locked_until:
                remaining = int((entry.locked_until - now).total_seconds())
                return True, remaining
            
            # Reset window if expired
            if self._is_window_expired(entry):
                entry.attempts = 0
                entry.window_start = now
                entry.locked_until = None
            
            # Increment attempts
            entry.attempts += 1
            
            # Check if should lock
            if entry.attempts >= self.max_attempts:
                entry.locked_until = now + timedelta(minutes=self.lockout_minutes)
                lockout_seconds = self.lockout_minutes * 60
                return True, lockout_seconds
            
            return False, None
    
    def record_successful_login(self, email: str) -> None:
        """Reset rate limit tracking after successful login."""
        with self._lock:
            email_lower = email.lower()
            if email_lower in self._entries:
                del self._entries[email_lower]
    
    def get_remaining_attempts(self, email: str) -> int:
        """Get the number of remaining login attempts before lockout."""
        with self._lock:
            entry = self._get_entry(email)
            
            # If window expired, full attempts available
            if self._is_window_expired(entry):
                return self.max_attempts
            
            return max(0, self.max_attempts - entry.attempts)
    
    def clear(self) -> None:
        """Clear all rate limit entries (for testing)."""
        with self._lock:
            self._entries.clear()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    if _rate_limiter:
        _rate_limiter.clear()
    _rate_limiter = None
