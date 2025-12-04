"""
Redis Cache Service for Viral Clip Generation.

Provides persistent caching for:
- LLM responses
- Analysis results
- Clip candidates
"""
import json
from typing import Any, Optional

import structlog
import redis

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Redis client singleton
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create Redis client singleton."""
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Test connection
        _redis_client.ping()
        logger.info("cache.redis_connected", url=settings.redis_url)
        return _redis_client
    except Exception as e:
        logger.warning("cache.redis_connection_failed", error=str(e))
        _redis_client = None
        return None


def get_cached(key: str, prefix: str = "virality") -> Optional[dict]:
    """
    Get cached value from Redis.
    
    Args:
        key: Cache key
        prefix: Key prefix for namespacing
    
    Returns:
        Cached dict or None if not found
    """
    client = get_redis_client()
    if not client:
        return None
    
    full_key = f"{prefix}:{key}"
    
    try:
        data = client.get(full_key)
        if data:
            logger.info("cache.hit", key=full_key)
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning("cache.get_failed", key=full_key, error=str(e))
        return None


def set_cached(
    key: str,
    data: dict,
    prefix: str = "virality",
    ttl: Optional[int] = None,
) -> bool:
    """
    Set cached value in Redis.
    
    Args:
        key: Cache key
        data: Data to cache (must be JSON serializable)
        prefix: Key prefix for namespacing
        ttl: Time to live in seconds (default from settings)
    
    Returns:
        True if successful, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    full_key = f"{prefix}:{key}"
    cache_ttl = ttl or settings.redis_cache_ttl
    
    try:
        client.setex(full_key, cache_ttl, json.dumps(data))
        logger.info("cache.set", key=full_key, ttl=cache_ttl)
        return True
    except Exception as e:
        logger.warning("cache.set_failed", key=full_key, error=str(e))
        return False


def delete_cached(key: str, prefix: str = "virality") -> bool:
    """Delete cached value from Redis."""
    client = get_redis_client()
    if not client:
        return False
    
    full_key = f"{prefix}:{key}"
    
    try:
        client.delete(full_key)
        logger.info("cache.deleted", key=full_key)
        return True
    except Exception as e:
        logger.warning("cache.delete_failed", key=full_key, error=str(e))
        return False


def clear_cache(prefix: str = "virality") -> int:
    """
    Clear all cached values with given prefix.
    
    Returns:
        Number of keys deleted
    """
    client = get_redis_client()
    if not client:
        return 0
    
    try:
        pattern = f"{prefix}:*"
        keys = client.keys(pattern)
        if keys:
            deleted = client.delete(*keys)
            logger.info("cache.cleared", prefix=prefix, count=deleted)
            return deleted
        return 0
    except Exception as e:
        logger.warning("cache.clear_failed", prefix=prefix, error=str(e))
        return 0


def get_cache_stats(prefix: str = "virality") -> dict:
    """Get cache statistics."""
    client = get_redis_client()
    if not client:
        return {"connected": False, "keys": 0}
    
    try:
        pattern = f"{prefix}:*"
        keys = client.keys(pattern)
        info = client.info("memory")
        return {
            "connected": True,
            "keys": len(keys),
            "used_memory": info.get("used_memory_human", "unknown"),
        }
    except Exception as e:
        logger.warning("cache.stats_failed", error=str(e))
        return {"connected": False, "keys": 0, "error": str(e)}
