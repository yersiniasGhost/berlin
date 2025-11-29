"""
Simple Caching Utilities with TTL Support
Provides time-based caching for frequently accessed data.
"""

import time
from typing import Any, Dict, Optional, Tuple
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Time-based cache with TTL (Time To Live) support.

    Provides simple in-memory caching with automatic expiration
    for frequently accessed data like configuration files, schemas, etc.
    """

    def __init__(self, ttl: int = 300, name: str = 'default'):
        """
        Initialize cache manager.

        Args:
            ttl: Time-to-live in seconds (default: 300 = 5 minutes)
            name: Name of this cache instance for logging
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, timestamp)
        self.ttl = ttl
        self.name = name
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        if key not in self._cache:
            self._misses += 1
            logger.debug(f"Cache miss [{self.name}]: {key}")
            return None

        value, timestamp = self._cache[key]
        age = time.time() - timestamp

        if age > self.ttl:
            # Expired, remove from cache
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache expired [{self.name}]: {key} (age: {age:.1f}s)")
            return None

        # Cache hit
        self._hits += 1
        logger.debug(f"Cache hit [{self.name}]: {key} (age: {age:.1f}s)")
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Cache value with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, time.time())
        logger.debug(f"Cache set [{self.name}]: {key}")

    def delete(self, key: str) -> bool:
        """
        Delete a specific cache entry.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache delete [{self.name}]: {key}")
            return True
        return False

    def clear(self) -> None:
        """Clear all cached data."""
        count = len(self._cache)
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info(f"Cache cleared [{self.name}]: {count} entries removed")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'name': self.name,
            'size': len(self._cache),
            'ttl': self.ttl,
            'hits': self._hits,
            'misses': self._misses,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2)
        }

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cache cleanup [{self.name}]: removed {len(expired_keys)} expired entries")

        return len(expired_keys)

    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (regardless of expiration)."""
        return key in self._cache


def cached(ttl: int = 300, cache_instance: Optional[CacheManager] = None):
    """
    Decorator for caching function results with TTL.

    Args:
        ttl: Time-to-live in seconds
        cache_instance: Optional CacheManager instance to use

    Example:
        @cached(ttl=600)
        def expensive_function(param1, param2):
            # ... expensive computation ...
            return result
    """
    def decorator(func):
        # Create cache instance if not provided
        cache = cache_instance or CacheManager(ttl=ttl, name=func.__name__)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            # Note: This only works for hashable arguments
            try:
                cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            except TypeError:
                # If arguments aren't hashable, skip caching
                logger.warning(f"Cannot cache {func.__name__}: unhashable arguments")
                return func(*args, **kwargs)

            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Not in cache, call function
            result = func(*args, **kwargs)

            # Cache the result
            cache.set(cache_key, result)

            return result

        # Attach cache instance to wrapper for inspection
        wrapper.cache = cache
        return wrapper

    return decorator


# Global cache instances for common use cases
indicator_schema_cache = CacheManager(ttl=600, name='indicator_schemas')  # 10 minutes
config_cache = CacheManager(ttl=300, name='configs')  # 5 minutes
data_cache = CacheManager(ttl=180, name='data')  # 3 minutes
