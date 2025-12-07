"""
CAPTCHA verification service for reCAPTCHA v2.

Requirements: 9.3
- WHEN a user submits the registration form THEN the Auth_Page SHALL require 
  completion of a CAPTCHA challenge
"""
import httpx
from typing import Tuple

from app.core.config import get_settings

# Google reCAPTCHA verification URL
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha(token: str) -> Tuple[bool, str]:
    """
    Verify a reCAPTCHA token with Google's API.
    
    Args:
        token: The reCAPTCHA response token from the client
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    settings = get_settings()
    
    # If CAPTCHA is disabled, skip verification
    if not settings.recaptcha_enabled:
        return True, ""
    
    # If no secret key is configured, skip verification (development mode)
    if not settings.recaptcha_secret_key:
        return True, ""
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                RECAPTCHA_VERIFY_URL,
                data={
                    "secret": settings.recaptcha_secret_key,
                    "response": token,
                }
            )
            
            if response.status_code != 200:
                return False, "Failed to verify CAPTCHA"
            
            data = response.json()
            
            if data.get("success"):
                return True, ""
            
            # Handle specific error codes
            error_codes = data.get("error-codes", [])
            if "timeout-or-duplicate" in error_codes:
                return False, "CAPTCHA expired. Please try again."
            elif "invalid-input-response" in error_codes:
                return False, "Invalid CAPTCHA response. Please try again."
            else:
                return False, "CAPTCHA verification failed. Please try again."
                
    except Exception as e:
        # Log the error but return a generic message
        print(f"CAPTCHA verification error: {e}")
        return False, "CAPTCHA verification failed. Please try again."


def is_captcha_required() -> bool:
    """
    Check if CAPTCHA verification is required.
    
    CAPTCHA is required when:
    1. RECAPTCHA_ENABLED is set to true
    2. AND RECAPTCHA_SECRET_KEY is configured
    
    Returns:
        True if CAPTCHA is required, False otherwise
    """
    settings = get_settings()
    return settings.recaptcha_enabled and bool(settings.recaptcha_secret_key)
