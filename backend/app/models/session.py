"""
Session registry — lightweight in-memory registry of active session IDs + tokens.

LangGraph's MemorySaver (in builder.py) now owns all session STATE.
This module tracks session ownership: each session_id is paired with a
cryptographically secure token that the client must present to connect.
For production, replace with Redis.
"""

import hmac
import time
from typing import Dict, Optional


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


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[SessionRegistry] = None


def get_session_registry() -> SessionRegistry:
    global _registry
    if _registry is None:
        from app.config import get_settings
        settings = get_settings()
        _registry = SessionRegistry(ttl_seconds=settings.session_store_ttl_seconds)
    return _registry


# ── Backward-compat shim for routes.py ───────────────────────────────────────
# routes.py calls get_session_store().get() / .delete().
# These thin wrappers delegate to the graph's checkpointer for state.

class _SessionStoreShim:
    """
    Thin compatibility layer so routes.py doesn't need changes.
    State reads go to the LangGraph checkpointer; delete also clears it.
    """

    def get(self, session_id: str):
        """Returns a minimal state dict from the graph's checkpoint, or None."""
        try:
            from app.graph.builder import get_compiled_graph
            graph = get_compiled_graph()
            snapshot = graph.get_state({"configurable": {"thread_id": session_id}})
            if snapshot and snapshot.values:
                return snapshot.values
        except Exception:
            pass
        return None

    async def delete(self, session_id: str) -> None:
        from app.graph.builder import clear_session_checkpoint
        await clear_session_checkpoint(session_id)
        get_session_registry().remove(session_id)


_shim: Optional[_SessionStoreShim] = None


def get_session_store() -> _SessionStoreShim:
    """Backward-compat accessor used by routes.py."""
    global _shim
    if _shim is None:
        _shim = _SessionStoreShim()
    return _shim
