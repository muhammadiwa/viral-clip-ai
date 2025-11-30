from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict, constr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: constr(min_length=6, max_length=72)


class UserOut(UserBase):
    id: int
    credits: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
