from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    credits: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VideoSourceBase(BaseModel):
    id: int
    title: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str

    class Config:
        from_attributes = True
