"""User preference API routes for managing theme and language settings."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User, UserPreference
from app.schemas.user_preference import UserPreferenceOut, UserPreferenceUpdate

router = APIRouter(prefix="/users/preferences", tags=["user-preferences"])


@router.get("", response_model=UserPreferenceOut)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user preferences. Creates default preferences if none exist."""
    preference = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == current_user.id)
        .first()
    )
    
    if not preference:
        # Create default preferences for the user
        preference = UserPreference(
            user_id=current_user.id,
            theme="light",
            language="en",
        )
        db.add(preference)
        db.commit()
        db.refresh(preference)
    
    return preference


@router.put("", response_model=UserPreferenceOut)
def update_preferences(
    preferences_in: UserPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user preferences (theme, language)."""
    preference = (
        db.query(UserPreference)
        .filter(UserPreference.user_id == current_user.id)
        .first()
    )
    
    if not preference:
        # Create preferences if they don't exist
        preference = UserPreference(
            user_id=current_user.id,
            theme=preferences_in.theme or "light",
            language=preferences_in.language or "en",
        )
        db.add(preference)
    else:
        # Update existing preferences
        if preferences_in.theme is not None:
            preference.theme = preferences_in.theme
        if preferences_in.language is not None:
            preference.language = preferences_in.language
    
    db.commit()
    db.refresh(preference)
    return preference
