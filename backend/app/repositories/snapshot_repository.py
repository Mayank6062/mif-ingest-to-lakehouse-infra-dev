"""
Snapshot Repository — Persistence layer for snapshots.

This module provides:
- SnapshotRepository: in-memory storage (Phase 1)
- Future: SQLAlchemy models for database persistence (Phase 2)
"""

from typing import List, Optional, Dict
from datetime import datetime
from app.models.state_v2 import Snapshot, SnapshotMetadata


class SnapshotRepository:
    """
    In-memory snapshot repository (Phase 1).
    
    In Phase 2, will be backed by:
    ```sql
    CREATE TABLE snapshots (
        snapshot_id VARCHAR(64) PRIMARY KEY,
        draft_id VARCHAR(64),
        parent_snapshot_id VARCHAR(64),
        timestamp TIMESTAMP,
        operation VARCHAR(64),
        user_action TEXT,
        draft_state JSONB,
        created_at TIMESTAMP
    );
    ```
    """
    
    def __init__(self):
        """Initialize in-memory storage."""
        self._store: Dict[str, Snapshot] = {}
        self._draft_snapshots: Dict[str, List[str]] = {}  # draft_id → [snapshot_ids]
    
    def save(self, snapshot: Snapshot) -> None:
        """Save snapshot to storage."""
        snapshot_id = snapshot['snapshot_id']
        draft_id = snapshot['draft_id']
        
        self._store[snapshot_id] = snapshot
        
        # Update index
        if draft_id not in self._draft_snapshots:
            self._draft_snapshots[draft_id] = []
        
        if snapshot_id not in self._draft_snapshots[draft_id]:
            self._draft_snapshots[draft_id].append(snapshot_id)
    
    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        """Retrieve snapshot from storage."""
        return self._store.get(snapshot_id)
    
    def delete(self, snapshot_id: str) -> bool:
        """Delete snapshot from storage."""
        if snapshot_id not in self._store:
            return False
        
        snapshot = self._store[snapshot_id]
        draft_id = snapshot['draft_id']
        
        del self._store[snapshot_id]
        
        # Update index
        if draft_id in self._draft_snapshots:
            self._draft_snapshots[draft_id] = [
                sid for sid in self._draft_snapshots[draft_id]
                if sid != snapshot_id
            ]
        
        return True
    
    def list_by_draft(self, draft_id: str) -> List[Snapshot]:
        """Get all snapshots for a draft (in chronological order)."""
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        return [
            self._store[sid] for sid in snapshot_ids
            if sid in self._store
        ]
    
    def get_metadata_by_draft(self, draft_id: str) -> List[SnapshotMetadata]:
        """Get metadata (not full snapshots) for all snapshots of a draft."""
        snapshots = self.list_by_draft(draft_id)
        return [
            SnapshotMetadata(
                snapshot_id=s['snapshot_id'],
                draft_id=s['draft_id'],
                parent_snapshot_id=s.get('parent_snapshot_id'),
                timestamp=s['timestamp'],
                operation=s.get('operation'),
                user_action=s.get('user_action'),
            )
            for s in snapshots
        ]
    
    def get_latest_by_draft(self, draft_id: str) -> Optional[Snapshot]:
        """Get the most recent snapshot for a draft."""
        snapshots = self.list_by_draft(draft_id)
        if not snapshots:
            return None
        return snapshots[-1]
    
    def count_by_draft(self, draft_id: str) -> int:
        """Get count of snapshots for a draft."""
        return len(self._draft_snapshots.get(draft_id, []))
    
    def count(self) -> int:
        """Get total count of snapshots."""
        return len(self._store)
    
    def exists(self, snapshot_id: str) -> bool:
        """Check if snapshot exists."""
        return snapshot_id in self._store
    
    def delete_by_draft(self, draft_id: str) -> int:
        """Delete all snapshots for a draft. Returns count deleted."""
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        count = len(snapshot_ids)
        
        for snapshot_id in snapshot_ids:
            self._store.pop(snapshot_id, None)
        
        self._draft_snapshots.pop(draft_id, None)
        
        return count
