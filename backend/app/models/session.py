"""
Session registry — authentication token storage with Redis persistence.

This module provides:
1. SessionRegistry — in-memory fallback for local development
2. RedisSessionRegistry — Redis-backed storage for production persistence
3. Dynamic registry selection based on USE_REDIS_CHECKPOINTER flag

When Redis is enabled, session tokens survive backend restarts. When disabled,
tokens are stored in-memory (ephemeral, lost on restart).
"""

import hmac
import time
import json
from typing import Dict, Optional
from datetime import timedelta


class SessionRegistry:
    """Tracks active session IDs, their auth tokens, and creation time (TTL/cleanup)."""

    def __init__(self, ttl_seconds: int = 3600):
        # session_id → {"token": str, "created_at": float}
        self._sessions: Dict[str, dict] = {}
        self.ttl = ttl_seconds

    def register(self, session_id: str, token: str) -> None:
        """Register a new session with its ownership token."""
        self._sessions[session_id] = {"token": token, "created_at": time.time()}

    def validate_token(self, session_id: str, token: str) -> bool:
        """
        Return True only when all three conditions hold:
          1. session_id exists in the registry
          2. the session has not exceeded TTL
          3. the supplied token matches the stored token (constant-time compare)
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            return False
        if time.time() - entry["created_at"] > self.ttl:
            self.remove(session_id)
            return False
        # hmac.compare_digest prevents timing-based token enumeration
        return hmac.compare_digest(entry["token"], token)

    def exists(self, session_id: str) -> bool:
        entry = self._sessions.get(session_id)
        if entry is None:
            return False
        if time.time() - entry["created_at"] > self.ttl:
            self.remove(session_id)
            return False
        return True

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def all_ids(self) -> list[str]:
        return list(self._sessions.keys())


class RedisSessionRegistry:
    """
    Redis-backed session registry — tokens persist across backend restarts.
    Requires async/await for all operations when using AsyncShallowRedisSaver.
    """

    def __init__(self, redis_client, ttl_seconds: int = 3600):
        """
        Initialize with a Redis async client (from AsyncShallowRedisSaver context).
        ttl_seconds: expiration time for stored tokens.
        """
        self.redis = redis_client
        self.ttl = ttl_seconds
        self.key_prefix = "glue_session:token:"

    async def register(self, session_id: str, token: str) -> None:
        """Store token in Redis with TTL."""
        key = f"{self.key_prefix}{session_id}"
        payload = json.dumps({"token": token, "created_at": time.time()})
        await self.redis.setex(key, self.ttl, payload)

    async def validate_token(self, session_id: str, token: str) -> bool:
        """Validate token against Redis storage."""
        key = f"{self.key_prefix}{session_id}"
        stored = await self.redis.get(key)
        if not stored:
            return False
        try:
            data = json.loads(stored)
            # hmac.compare_digest prevents timing-based token enumeration
            return hmac.compare_digest(data["token"], token)
        except (json.JSONDecodeError, KeyError):
            return False

    async def exists(self, session_id: str) -> bool:
        """Check if token exists in Redis."""
        key = f"{self.key_prefix}{session_id}"
        return await self.redis.exists(key) > 0

    async def remove(self, session_id: str) -> None:
        """Delete token from Redis."""
        key = f"{self.key_prefix}{session_id}"
        await self.redis.delete(key)

    async def all_ids(self) -> list[str]:
        """Retrieve all active session IDs from Redis."""
        pattern = f"{self.key_prefix}*"
        keys = await self.redis.keys(pattern)
        return [k.decode() if isinstance(k, bytes) else k for k in keys]


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[object] = None  # Can be SessionRegistry or RedisSessionRegistry


def get_session_registry():
    """Get the active session registry (memory or Redis based on config)."""
    global _registry
    if _registry is None:
        from app.config import get_settings
        settings = get_settings()
        
        if settings.use_redis_checkpointer:
            # Redis mode — requires async context (token operations are async)
            # For now, return a wrapper that provides sync-safe access
            # The actual Redis instance is injected via set_redis_registry()
            _registry = SessionRegistry(ttl_seconds=settings.session_store_ttl_seconds)
        else:
            # Memory mode — in-memory storage
            _registry = SessionRegistry(ttl_seconds=settings.session_store_ttl_seconds)
    return _registry


def set_redis_registry(redis_registry: RedisSessionRegistry) -> None:
    """
    Set the Redis-backed registry. Called from main.py lifespan when
    USE_REDIS_CHECKPOINTER=true and Redis connection is available.
    """
    global _registry
    _registry = redis_registry


# ── Backward-compat shim for routes.py ───────────────────────────────────────
# routes.py calls get_session_store().get() / .delete().
# These thin wrappers delegate to the graph's checkpointer for state.

class _SessionStoreShim:
    """
    Thin compatibility layer so routes.py doesn't need changes.
    State reads go to the LangGraph checkpointer; delete also clears it.
    """

    async def get(self, session_id: str):
        """Returns a minimal state dict from the graph's checkpoint, or None."""
        try:
            from app.graph.builder import get_compiled_graph
            graph = get_compiled_graph()
            snapshot = await graph.aget_state({"configurable": {"thread_id": session_id}})
            if snapshot and snapshot.values:
                return snapshot.values
        except Exception:
            pass
        return None

    async def delete(self, session_id: str) -> None:
        from app.graph.builder import clear_session_checkpoint
        await clear_session_checkpoint(session_id)
        registry = get_session_registry()
        if isinstance(registry, RedisSessionRegistry):
            await registry.remove(session_id)
        else:
            registry.remove(session_id)


_shim: Optional[_SessionStoreShim] = None


def get_session_store() -> _SessionStoreShim:
    """Backward-compat accessor used by routes.py."""
    global _shim
    if _shim is None:
        _shim = _SessionStoreShim()
    return _shim
