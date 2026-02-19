"""In-memory TTL cache for YouTube API responses.

Persists across warm Lambda invocations via module-level state.
Cache keys are SHA-256 digests to avoid storing medical topics in logs.
"""

import hashlib
import os
import time
from typing import Any


_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))

_store: dict[str, dict[str, Any]] = {}


def make_key(topic: str) -> str:
    """Return a SHA-256 hex digest of the topic for use as a cache key."""
    return hashlib.sha256(topic.lower().strip().encode()).hexdigest()


def get(key: str) -> Any | None:
    """Return the cached value for key, or None if missing or expired."""
    entry = _store.get(key)
    if entry is None:
        return None
    if time.monotonic() > entry["expires_at"]:
        del _store[key]
        return None
    return entry["value"]


def put(key: str, value: Any) -> None:
    """Store value under key with a TTL-based expiry."""
    _store[key] = {
        "value": value,
        "expires_at": time.monotonic() + _TTL_SECONDS,
    }
