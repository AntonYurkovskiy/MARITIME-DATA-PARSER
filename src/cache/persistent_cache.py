"""
Persistent cache for API dictionaries and lookup results.

Uses SQLite for thread-safe persistent storage with TTL support.
"""

import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# Default TTL: 24 hours
DEFAULT_TTL = 24 * 60 * 60  # seconds
CACHE_DB_PATH = Path(__file__).parent.parent.parent / "cache.db"


class PersistentCache:
    """Thread-safe persistent cache using SQLite."""
    
    def __init__(self, db_path: Optional[Path] = None, ttl: int = DEFAULT_TTL):
        self.db_path = db_path or CACHE_DB_PATH
        self.ttl = ttl
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with cache table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.commit()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if exists and not expired."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT value, timestamp FROM cache WHERE key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    return None
                
                value_str, timestamp = row
                
                # Check TTL
                if time.time() - timestamp > self.ttl:
                    # Expired, delete and return None
                    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                    conn.commit()
                    return None
                
                return json.loads(value_str)
        except Exception as e:
            logger.warning(f"Cache get failed for key '{key}': {e}")
            return None
    
    def set(self, key: str, value: Any):
        """Set value in cache with current timestamp."""
        try:
            value_str = json.dumps(value)
            timestamp = time.time()
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
                    (key, value_str, timestamp)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Cache set failed for key '{key}': {e}")
    
    def delete(self, key: str):
        """Delete specific key from cache."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
        except Exception as e:
            logger.warning(f"Cache delete failed for key '{key}': {e}")
    
    def clear(self):
        """Clear all cache entries."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM cache")
                conn.commit()
            logger.info("Cache cleared")
        except Exception as e:
            logger.warning(f"Cache clear failed: {e}")
    
    def cleanup_expired(self):
        """Remove all expired entries from cache."""
        try:
            cutoff_time = time.time() - self.ttl
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "DELETE FROM cache WHERE timestamp < ?",
                    (cutoff_time,)
                )
                deleted = cursor.rowcount
                conn.commit()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired cache entries")
        except Exception as e:
            logger.warning(f"Cache cleanup failed: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM cache")
                total = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE timestamp < ?",
                    (time.time() - self.ttl,)
                )
                expired = cursor.fetchone()[0]
                
                return {
                    "total_entries": total,
                    "expired_entries": expired,
                    "valid_entries": total - expired,
                    "ttl_hours": self.ttl / 3600
                }
        except Exception as e:
            logger.warning(f"Cache stats failed: {e}")
            return {"error": str(e)}


# Global cache instance
_global_cache: Optional[PersistentCache] = None


def get_cache(ttl: int = DEFAULT_TTL, force_refresh: bool = False) -> PersistentCache:
    """Get or create global cache instance."""
    global _global_cache
    
    if _global_cache is None or force_refresh:
        _global_cache = PersistentCache(ttl=ttl)
    
    return _global_cache


def cached_result(key_prefix: str = "", ttl: int = DEFAULT_TTL):
    """Decorator for caching function results.
    
    Args:
        key_prefix: Prefix for cache key (e.g., function name)
        ttl: Time-to-live in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            cache_key = cache_key.replace(" ", "_")[:500]  # Limit key length
            
            cache = get_cache(ttl=ttl)
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            logger.debug(f"Cache miss for {func.__name__}, result cached")
            
            return result
        return wrapper
    return decorator


def invalidate_cache():
    """Invalidate global cache instance."""
    global _global_cache
    _global_cache = None
    logger.info("Global cache invalidated")


class ProcessedFilesTracker:
    """Tracks which files have been successfully processed to allow resume after interruption."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or CACHE_DB_PATH
        self._init_table()

    def _init_table(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    filename TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    processed_at REAL NOT NULL
                )
            """)
            conn.commit()

    def is_processed(self, filename: str) -> bool:
        """Return True if file was already successfully processed."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM processed_files WHERE filename = ? AND status = 'success'",
                    (filename,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.warning(f"ProcessedFilesTracker.is_processed failed for '{filename}': {e}")
            return False

    def mark_processed(self, filename: str, status: str = "success"):
        """Mark file as processed with given status."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO processed_files (filename, status, processed_at) VALUES (?, ?, ?)",
                    (filename, status, time.time())
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"ProcessedFilesTracker.mark_processed failed for '{filename}': {e}")

    def get_stats(self) -> dict:
        """Return counts by status."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "SELECT status, COUNT(*) FROM processed_files GROUP BY status"
                )
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.warning(f"ProcessedFilesTracker.get_stats failed: {e}")
            return {}

    def reset(self):
        """Clear all records (use for full reprocess)."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("DELETE FROM processed_files")
                conn.commit()
            logger.info("ProcessedFilesTracker reset: all records cleared")
        except Exception as e:
            logger.warning(f"ProcessedFilesTracker.reset failed: {e}")


_global_tracker: Optional["ProcessedFilesTracker"] = None


def get_processed_tracker() -> "ProcessedFilesTracker":
    """Get or create global ProcessedFilesTracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ProcessedFilesTracker()
    return _global_tracker


if __name__ == "__main__":
    # Test cache functionality
    cache = get_cache()
    
    # Test set/get
    cache.set("test_key", {"value": 123})
    result = cache.get("test_key")
    print(f"Test set/get: {result}")
    
    # Test stats
    stats = cache.get_stats()
    print(f"Cache stats: {stats}")
    
    # Test cleanup
    cache.cleanup_expired()
