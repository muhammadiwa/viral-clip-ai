from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, constr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: constr(min_length=6, max_length=72)


class UserOut(UserBase):
    id: int
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    credits: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
