"""
Snapshot Engine — Version management for draft workspaces.

This module provides:
- SnapshotEngine: create, manage, and restore snapshots
- Immutable point-in-time capture of draft state
- Undo/redo stack management
- Automatic snapshots on each operation

Snapshots enable:
- "Discard Last Change" UX
- Version history navigation
- Change tracking via diffs
- Data recovery from corruption
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.state_v2 import (
    Snapshot,
    DraftWorkspace,
    DraftFile,
    GlueJobEntry,
    ValidationReport,
    SnapshotMetadata,
)
from app.models.diff import DiffEngine, ChangeSet


class SnapshotEngine:
    """
    Create and manage snapshots of draft workspaces.
    
    Usage:
    ```python
    engine = SnapshotEngine()
    
    # Create a snapshot
    snapshot = engine.create_snapshot(
        draft_id="draft-123",
        operation="create_job",
        user_action="Created Glue job saptcc-multi-1",
        files=current_files,
        glue_jobs=current_jobs,
        validation_reports=current_reports,
        parent_snapshot_id=last_snapshot_id,
    )
    
    # Restore to previous state
    restored_files, restored_jobs = engine.restore_snapshot(snapshot_id)
    
    # Get history of snapshots
    history = engine.get_snapshot_history(draft_id)
    
    # Compute diff between snapshots
    changeset = engine.get_changeset(from_id, to_id)
    ```
    """
    
    def __init__(self):
        """Initialize snapshot engine (in-memory storage)."""
        # In-memory storage: snapshot_id → Snapshot
        self._snapshots: Dict[str, Snapshot] = {}
        # Draft-to-snapshots index: draft_id → [snapshot_id, ...]
        self._draft_snapshots: Dict[str, List[str]] = {}
        # Changesets: changeset_id → ChangeSet
        self._changesets: Dict[str, ChangeSet] = {}
    
    def create_snapshot(
        self,
        draft_id: str,
        operation: str,
        user_action: str,
        files: List[DraftFile],
        glue_jobs: List[GlueJobEntry],
        validation_reports: List[ValidationReport],
        parent_snapshot_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Snapshot:
        """
        Create a new snapshot of draft state.
        
        Args:
            draft_id: which draft this snapshot is for
            operation: what triggered the snapshot (e.g., "create_job", "edit_file")
            user_action: human-readable description
            files: current files in draft
            glue_jobs: current glue jobs in draft
            validation_reports: current validation reports
            parent_snapshot_id: previous snapshot (for undo/redo chain)
            metadata: additional context
        
        Returns:
            Created snapshot
        """
        snapshot_id = str(uuid.uuid4())
        now = datetime.now()
        
        snapshot: Snapshot = {
            'snapshot_id': snapshot_id,
            'draft_id': draft_id,
            'parent_snapshot_id': parent_snapshot_id,
            'timestamp': now,
            'operation': operation,
            'user_action': user_action,
            'files': files,
            'glue_jobs': glue_jobs,
            'validation_reports': validation_reports,
            'metadata': metadata or {},
        }
        
        # Store snapshot
        self._snapshots[snapshot_id] = snapshot
        
        # Update draft index
        if draft_id not in self._draft_snapshots:
            self._draft_snapshots[draft_id] = []
        self._draft_snapshots[draft_id].append(snapshot_id)
        
        return snapshot
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Retrieve a snapshot by ID."""
        return self._snapshots.get(snapshot_id)
    
    def restore_snapshot(
        self, 
        snapshot_id: str
    ) -> tuple[List[DraftFile], List[GlueJobEntry], List[ValidationReport]]:
        """
        Restore draft state from a snapshot.
        
        Returns:
            Tuple of (files, glue_jobs, validation_reports) at that snapshot
        
        Raises:
            ValueError if snapshot not found
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        
        return (
            snapshot.get('files', []),
            snapshot.get('glue_jobs', []),
            snapshot.get('validation_reports', []),
        )
    
    def get_snapshot_history(self, draft_id: str) -> List[SnapshotMetadata]:
        """
        Get metadata for all snapshots of a draft (in chronological order).
        
        Returns:
            List of SnapshotMetadata (not full snapshots, just metadata)
        """
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        metadata_list: List[SnapshotMetadata] = []
        
        for snapshot_id in snapshot_ids:
            snapshot = self._snapshots.get(snapshot_id)
            if snapshot:
                metadata_list.append(SnapshotMetadata(
                    snapshot_id=snapshot_id,
                    draft_id=draft_id,
                    parent_snapshot_id=snapshot.get('parent_snapshot_id'),
                    timestamp=snapshot.get('timestamp'),
                    operation=snapshot.get('operation'),
                    user_action=snapshot.get('user_action'),
                ))
        
        return metadata_list
    
    def discard_last_change(self, draft_id: str) -> Optional[Snapshot]:
        """
        Undo the last operation by reverting to previous snapshot.
        
        Implementation for Rule "User sees 'Discard Last Change', not snapshots".
        
        Returns:
            Previous snapshot (what draft should restore to)
            None if no previous snapshot exists
        """
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        if len(snapshot_ids) < 2:
            return None  # Only one snapshot or none
        
        # Return second-to-last snapshot
        previous_id = snapshot_ids[-2]
        return self._snapshots.get(previous_id)
    
    def get_changeset_between(
        self,
        from_snapshot_id: str,
        to_snapshot_id: str,
    ) -> Optional[ChangeSet]:
        """
        Compute changeset (diff) between two snapshots.
        
        Returns:
            ChangeSet with all changes
            None if either snapshot not found
        """
        from_snap = self._snapshots.get(from_snapshot_id)
        to_snap = self._snapshots.get(to_snapshot_id)
        
        if not from_snap or not to_snap:
            return None
        
        changeset_id = str(uuid.uuid4())
        
        # Compute diff using DiffEngine
        changeset = DiffEngine.compute_changeset(
            changeset_id=changeset_id,
            from_snapshot_id=from_snapshot_id,
            to_snapshot_id=to_snapshot_id,
            old_files=from_snap.get('files', []),
            new_files=to_snap.get('files', []),
            old_jobs=from_snap.get('glue_jobs', []),
            new_jobs=to_snap.get('glue_jobs', []),
        )
        
        # Cache changeset
        self._changesets[changeset_id] = changeset
        
        return changeset
    
    def get_changeset(self, changeset_id: str) -> Optional[ChangeSet]:
        """Retrieve a cached changeset."""
        return self._changesets.get(changeset_id)
    
    def prune_snapshots(
        self,
        draft_id: str,
        keep_count: int = 50
    ) -> List[str]:
        """
        Delete old snapshots, keeping only the most recent N.
        
        Args:
            draft_id: which draft to prune
            keep_count: how many recent snapshots to keep
        
        Returns:
            List of deleted snapshot IDs
        """
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        if len(snapshot_ids) <= keep_count:
            return []
        
        # Delete oldest snapshots
        to_delete = snapshot_ids[:-keep_count]
        deleted_ids = []
        
        for snapshot_id in to_delete:
            if snapshot_id in self._snapshots:
                del self._snapshots[snapshot_id]
                deleted_ids.append(snapshot_id)
        
        # Update index
        self._draft_snapshots[draft_id] = snapshot_ids[-keep_count:]
        
        return deleted_ids
    
    def cleanup_draft(self, draft_id: str) -> int:
        """
        Delete all snapshots for a draft (when draft is merged/abandoned).
        
        Returns:
            Count of deleted snapshots
        """
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        count = len(snapshot_ids)
        
        for snapshot_id in snapshot_ids:
            self._snapshots.pop(snapshot_id, None)
        
        self._draft_snapshots.pop(draft_id, None)
        
        return count
    
    def get_statistics(self, draft_id: str) -> Dict[str, Any]:
        """Get statistics about snapshots for a draft."""
        snapshot_ids = self._draft_snapshots.get(draft_id, [])
        snapshots = [self._snapshots.get(sid) for sid in snapshot_ids]
        snapshots = [s for s in snapshots if s]
        
        total_files = 0
        total_jobs = 0
        
        for snapshot in snapshots:
            total_files = max(total_files, len(snapshot.get('files', [])))
            total_jobs = max(total_jobs, len(snapshot.get('glue_jobs', [])))
        
        return {
            'draft_id': draft_id,
            'snapshot_count': len(snapshots),
            'total_operations': len(snapshots),
            'max_files_in_snapshot': total_files,
            'max_jobs_in_snapshot': total_jobs,
            'first_snapshot_time': snapshots[0]['timestamp'] if snapshots else None,
            'last_snapshot_time': snapshots[-1]['timestamp'] if snapshots else None,
        }


class SnapshotManager:
    """
    Higher-level snapshot management (multi-draft, cleanup, etc).
    """
    
    def __init__(self, engine: SnapshotEngine):
        """Initialize with a SnapshotEngine."""
        self.engine = engine
    
    def create_auto_snapshot(
        self,
        draft_id: str,
        operation: str,
        user_action: str,
        draft_workspace: DraftWorkspace,
        parent_snapshot_id: Optional[str] = None,
    ) -> Snapshot:
        """
        Create a snapshot automatically after an operation.
        
        Extracts current state from draft_workspace.
        """
        return self.engine.create_snapshot(
            draft_id=draft_id,
            operation=operation,
            user_action=user_action,
            files=draft_workspace.get('files', []),
            glue_jobs=draft_workspace.get('glue_jobs', []),
            validation_reports=draft_workspace.get('validation_reports', []),
            parent_snapshot_id=parent_snapshot_id,
        )
    
    def undo_last_operation(
        self,
        draft_workspace: DraftWorkspace,
    ) -> bool:
        """
        Undo last operation in draft.
        
        Returns:
            True if undo succeeded, False if nothing to undo
        """
        previous_snapshot = self.engine.discard_last_change(draft_workspace['draft_id'])
        if not previous_snapshot:
            return False
        
        # Update draft_workspace with restored state
        draft_workspace['files'] = previous_snapshot.get('files', [])
        draft_workspace['glue_jobs'] = previous_snapshot.get('glue_jobs', [])
        draft_workspace['validation_reports'] = previous_snapshot.get('validation_reports', [])
        draft_workspace['updated_at'] = datetime.now()
        draft_workspace['last_change_timestamp'] = previous_snapshot['timestamp']
        
        return True
