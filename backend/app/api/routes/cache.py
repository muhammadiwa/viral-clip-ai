"""
Cache management endpoints.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.services import cache

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
def get_cache_stats(current_user: User = Depends(get_current_user)):
    """Get cache statistics."""
    return cache.get_cache_stats()


@router.delete("/virality")
def clear_virality_cache(current_user: User = Depends(get_current_user)):
    """Clear virality cache."""
    deleted = cache.clear_cache(prefix="virality")
    return {"deleted": deleted, "message": f"Cleared {deleted} cache keys"}
