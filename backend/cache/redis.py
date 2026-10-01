"""
Redis cache client wrapper.
Provides a unified interface for Redis operations.
"""
import logging
from typing import Optional
from django.conf import settings

logger = logging.getLogger('cache')

_redis_client = None


def get_redis_client() -> Optional[object]:
    """
    Get or create a Redis client connection.
    Returns None if Redis is unavailable.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

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


def reset_redis_client():
    """Reset the Redis client (for testing)."""
    global _redis_client
    _redis_client = None
