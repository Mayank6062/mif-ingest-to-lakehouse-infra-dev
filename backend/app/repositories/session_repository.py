"""
Session Repository — Persistence layer for sessions.

This module provides:
- SessionRepository: in-memory storage (Phase 1)
- Future: SQLAlchemy models for database persistence (Phase 2)

Repository pattern allows swapping storage backends without changing service layer.
"""

from typing import List, Optional, Dict
from app.models.state_v2 import Session


class SessionRepository:
    """
    In-memory session repository (Phase 1).
    
    In Phase 2, this will be replaced with SQLAlchemy models:
    ```python
    class SessionModel(Base):
        __tablename__ = "sessions"
        session_id = Column(String(64), primary_key=True)
        user_email = Column(String(255))
        message_history = Column(JSON)
        ...
    ```
    """
    
    def __init__(self):
        """Initialize in-memory storage."""
        self._store: Dict[str, Session] = {}
    
    def save(self, session: Session) -> None:
        """Save session to storage."""
        self._store[session['session_id']] = session
    
    def get(self, session_id: str) -> Optional[Session]:
        """Retrieve session from storage."""
        return self._store.get(session_id)
    
    def delete(self, session_id: str) -> bool:
        """Delete session from storage."""
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False
    
    def list_all(self) -> List[Session]:
        """Get all sessions."""
        return list(self._store.values())
    
    def count(self) -> int:
        """Get count of sessions."""
        return len(self._store)
    
    def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self._store
