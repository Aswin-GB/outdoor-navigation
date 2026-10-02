"""
Redis cache client wrapper.
Provides a unified interface for Redis operations.
Supports an in-memory fallback for environments without Redis.
"""
import logging
import time
from typing import Optional, Any
from django.conf import settings

logger = logging.getLogger('cache')

_redis_client = None
_memory_cache = {}

def get_redis_client() -> Optional[object]:
    """
    Get or create a Redis client connection.
    Returns None if Redis is unavailable.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.REDIS_URL:
        return None

    try:
        import redis
        client = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
        # Test connection
        client.ping()
        _redis_client = client
        logger.info("Redis connection established")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}")
        _redis_client = None
        return None

def get_cached_item(key: str) -> Optional[Any]:
    """Get item from Redis or in-memory fallback."""
    client = get_redis_client()
    if client:
        try:
            cached = client.get(key)
            if cached:
                import json
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis read failed: {e}")

    cached = _memory_cache.get(key)
    if cached is None:
        return None

    expires_at, value = cached
    if expires_at <= time.monotonic():
        _memory_cache.pop(key, None)
        return None
    return value

def set_cached_item(key: str, value: Any, ttl: int = 300) -> None:
    """Set item in Redis or a TTL-bound in-memory fallback."""
    client = get_redis_client()
    if client:
        try:
            import json
            client.setex(key, ttl, json.dumps(value))
            return
        except Exception as e:
            logger.warning(f"Redis write failed: {e}")

    _memory_cache[key] = (time.monotonic() + max(0, ttl), value)

def clear_cache() -> None:
    """Clear all cached items."""
    global _memory_cache
    if _redis_client:
        try:
            _redis_client.flushall()
        except Exception:
            pass
    _memory_cache.clear()
