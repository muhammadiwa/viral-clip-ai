"""User preference schemas for API request/response validation."""

from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict


class UserPreferenceBase(BaseModel):
    """Base user preference schema with common fields."""
    theme: Literal["light", "dark", "system"] = "light"
    language: str = "en"


class UserPreferenceOut(UserPreferenceBase):
    """Schema for user preference response."""
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class UserPreferenceUpdate(BaseModel):
    """Schema for updating user preferences."""
    theme: Optional[Literal["light", "dark", "system"]] = None
    language: Optional[str] = None
