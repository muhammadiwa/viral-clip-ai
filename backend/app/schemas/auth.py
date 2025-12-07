from pydantic import BaseModel, EmailStr
from typing import Optional


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GoogleAuthRequest(BaseModel):
    """Request body for Google OAuth authentication"""
    access_token: str


class GoogleUserInfo(BaseModel):
    """Google user info from OAuth"""
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    verified_email: bool = False


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password endpoint"""
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Response for forgot password endpoint"""
    message: str


class ResetPasswordRequest(BaseModel):
    """Request body for reset password endpoint"""
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    """Response for reset password endpoint"""
    message: str


class VerifyResetTokenResponse(BaseModel):
    """Response for verify reset token endpoint"""
    valid: bool
    message: str
