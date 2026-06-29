"""Cache module for persistent storage of API results."""

from src.cache.persistent_cache import (
    PersistentCache,
    get_cache,
    cached_result,
    invalidate_cache,
    is_cache_enabled,
    ProcessedFilesTracker,
    get_processed_tracker,
)

__all__ = [
    "PersistentCache",
    "get_cache",
    "cached_result",
    "invalidate_cache",
    "is_cache_enabled",
    "ProcessedFilesTracker",
    "get_processed_tracker",
]
