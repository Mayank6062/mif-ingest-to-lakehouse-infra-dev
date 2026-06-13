"""
Draft Workspace Repository — Persistence layer for draft workspaces.

This module provides:
- DraftWorkspaceRepository: in-memory storage (Phase 1)
- Future: SQLAlchemy models for database persistence (Phase 2)
"""

from typing import List, Optional, Dict
from app.models.state_v2 import DraftWorkspace, DraftWorkspaceStatus


class DraftWorkspaceRepository:
    """
    In-memory draft workspace repository (Phase 1).
    
    In Phase 2, will be backed by:
    ```sql
    CREATE TABLE draft_workspaces (
        draft_id VARCHAR(64) PRIMARY KEY,
        session_id VARCHAR(64),
        status VARCHAR(32),
        files JSONB,
        glue_jobs JSONB,
        validation_reports JSONB,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    );
    ```
    """
    
    def __init__(self):
        """Initialize in-memory storage."""
        self._store: Dict[str, DraftWorkspace] = {}
        self._session_drafts: Dict[str, List[str]] = {}  # session_id → [draft_ids]
    
    def save(self, draft: DraftWorkspace) -> None:
        """Save draft to storage."""
        draft_id = draft['draft_id']
        session_id = draft['session_id']
        
        self._store[draft_id] = draft
        
        # Update index
        if session_id not in self._session_drafts:
            self._session_drafts[session_id] = []
        
        if draft_id not in self._session_drafts[session_id]:
            self._session_drafts[session_id].append(draft_id)
    
    def get(self, draft_id: str) -> Optional[DraftWorkspace]:
        """Retrieve draft from storage."""
        return self._store.get(draft_id)
    
    def delete(self, draft_id: str) -> bool:
        """Delete draft from storage."""
        if draft_id not in self._store:
            return False
        
        draft = self._store[draft_id]
        session_id = draft['session_id']
        
        del self._store[draft_id]
        
        # Update index
        if session_id in self._session_drafts:
            self._session_drafts[session_id] = [
                did for did in self._session_drafts[session_id]
                if did != draft_id
            ]
        
        return True
    
    def list_by_session(self, session_id: str) -> List[DraftWorkspace]:
        """Get all drafts for a session."""
        draft_ids = self._session_drafts.get(session_id, [])
        return [
            self._store[did] for did in draft_ids
            if did in self._store
        ]
    
    def list_by_status(self, status: DraftWorkspaceStatus) -> List[DraftWorkspace]:
        """Get all drafts with a specific status."""
        return [
            draft for draft in self._store.values()
            if draft['status'] == status
        ]
    
    def count(self) -> int:
        """Get count of drafts."""
        return len(self._store)
    
    def exists(self, draft_id: str) -> bool:
        """Check if draft exists."""
        return draft_id in self._store
