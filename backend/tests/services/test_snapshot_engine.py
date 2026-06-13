"""
Unit tests for Snapshot Engine Service.

Tests:
- Snapshot creation
- Snapshot restoration
- Undo/redo operations
- History tracking
- Cleanup and pruning
"""

import pytest
from datetime import datetime
from app.services.snapshot_engine import SnapshotEngine, SnapshotManager
from app.models.state_v2 import (
    create_draft_workspace,
    create_validation_report,
)


class TestSnapshotEngineCreation:
    """Test snapshot creation."""
    
    def test_create_snapshot(self):
        """Test creating a snapshot."""
        engine = SnapshotEngine()
        
        files = [
            {
                'file_id': 'f1',
                'draft_id': 'draft-001',
                'path': 'saptcc/locals.tf',
                'content': 'locals {}',
                'file_type': 'terraform',
                'mtime': datetime.now(),
                'editable': True,
                'locked_by': None,
                'locked_at': None,
            }
        ]
        
        snapshot = engine.create_snapshot(
            draft_id="draft-001",
            operation="create_job",
            user_action="Created first job",
            files=files,
            glue_jobs=[],
            validation_reports=[],
        )
        
        assert snapshot['snapshot_id'] is not None
        assert snapshot['draft_id'] == "draft-001"
        assert snapshot['operation'] == "create_job"
        assert len(snapshot['files']) == 1
    
    def test_snapshots_indexed_by_draft(self):
        """Test that snapshots are indexed by draft."""
        engine = SnapshotEngine()
        
        # Create 2 snapshots for same draft
        snap1 = engine.create_snapshot(
            draft_id="draft-001",
            operation="create",
            user_action="Initial",
            files=[], glue_jobs=[], validation_reports=[]
        )
        
        snap2 = engine.create_snapshot(
            draft_id="draft-001",
            operation="add_job",
            user_action="Added job",
            files=[], glue_jobs=[], validation_reports=[],
            parent_snapshot_id=snap1['snapshot_id'],
        )
        
        history = engine.get_snapshot_history("draft-001")
        
        assert len(history) == 2
        assert history[0]['snapshot_id'] == snap1['snapshot_id']
        assert history[1]['snapshot_id'] == snap2['snapshot_id']


class TestSnapshotRestoration:
    """Test snapshot restoration."""
    
    def test_restore_snapshot(self):
        """Test restoring a snapshot."""
        engine = SnapshotEngine()
        
        files = [
            {
                'file_id': 'f1',
                'draft_id': 'draft-001',
                'path': 'saptcc/locals.tf',
                'content': 'locals { }',
                'file_type': 'terraform',
                'mtime': datetime.now(),
                'editable': True,
                'locked_by': None,
                'locked_at': None,
            }
        ]
        
        snapshot = engine.create_snapshot(
            draft_id="draft-001",
            operation="test",
            user_action="Test snapshot",
            files=files,
            glue_jobs=[],
            validation_reports=[],
        )
        
        restored_files, restored_jobs, restored_reports = engine.restore_snapshot(
            snapshot['snapshot_id']
        )
        
        assert len(restored_files) == 1
        assert restored_files[0]['path'] == 'saptcc/locals.tf'
    
    def test_restore_nonexistent_snapshot_raises(self):
        """Test that restoring nonexistent snapshot raises error."""
        engine = SnapshotEngine()
        
        with pytest.raises(ValueError):
            engine.restore_snapshot("nonexistent-snap-id")


class TestUndoRedoOperations:
    """Test undo/redo stack management."""
    
    def test_discard_last_change_single_snapshot(self):
        """Test undo when only one snapshot exists."""
        engine = SnapshotEngine()
        
        engine.create_snapshot(
            draft_id="draft-001",
            operation="create",
            user_action="Initial",
            files=[], glue_jobs=[], validation_reports=[]
        )
        
        result = engine.discard_last_change("draft-001")
        
        # Should return None (can't undo initial snapshot)
        assert result is None
    
    def test_discard_last_change_multiple_snapshots(self):
        """Test undo with multiple snapshots."""
        engine = SnapshotEngine()
        
        snap1 = engine.create_snapshot(
            draft_id="draft-001",
            operation="create",
            user_action="Initial",
            files=[], glue_jobs=[], validation_reports=[]
        )
        
        snap2 = engine.create_snapshot(
            draft_id="draft-001",
            operation="add_job",
            user_action="Added job",
            files=[], glue_jobs=[], validation_reports=[],
            parent_snapshot_id=snap1['snapshot_id'],
        )
        
        previous = engine.discard_last_change("draft-001")
        
        # Should return first snapshot
        assert previous is not None
        assert previous['snapshot_id'] == snap1['snapshot_id']


class TestSnapshotHistory:
    """Test history tracking."""
    
    def test_get_snapshot_history(self):
        """Test retrieving snapshot history."""
        engine = SnapshotEngine()
        
        # Create 3 snapshots
        for i in range(3):
            engine.create_snapshot(
                draft_id="draft-001",
                operation=f"op-{i}",
                user_action=f"Action {i}",
                files=[], glue_jobs=[], validation_reports=[]
            )
        
        history = engine.get_snapshot_history("draft-001")
        
        assert len(history) == 3
        for i, meta in enumerate(history):
            assert meta['operation'] == f"op-{i}"


class TestSnapshotCleanup:
    """Test pruning and cleanup."""
    
    def test_prune_snapshots(self):
        """Test pruning old snapshots."""
        engine = SnapshotEngine()
        
        # Create 10 snapshots
        for i in range(10):
            engine.create_snapshot(
                draft_id="draft-001",
                operation=f"op-{i}",
                user_action=f"Action {i}",
                files=[], glue_jobs=[], validation_reports=[]
            )
        
        # Prune, keeping only 5
        deleted_ids = engine.prune_snapshots("draft-001", keep_count=5)
        
        assert len(deleted_ids) == 5
        
        history = engine.get_snapshot_history("draft-001")
        assert len(history) == 5
    
    def test_cleanup_draft(self):
        """Test cleaning up all snapshots for a draft."""
        engine = SnapshotEngine()
        
        # Create 5 snapshots
        for i in range(5):
            engine.create_snapshot(
                draft_id="draft-001",
                operation=f"op-{i}",
                user_action=f"Action {i}",
                files=[], glue_jobs=[], validation_reports=[]
            )
        
        # Cleanup
        count = engine.cleanup_draft("draft-001")
        
        assert count == 5
        
        history = engine.get_snapshot_history("draft-001")
        assert len(history) == 0


class TestSnapshotStatistics:
    """Test statistics generation."""
    
    def test_get_statistics(self):
        """Test getting snapshot statistics."""
        engine = SnapshotEngine()
        
        # Create 3 snapshots
        for i in range(3):
            engine.create_snapshot(
                draft_id="draft-001",
                operation=f"op-{i}",
                user_action=f"Action {i}",
                files=[], glue_jobs=[], validation_reports=[]
            )
        
        stats = engine.get_statistics("draft-001")
        
        assert stats['draft_id'] == "draft-001"
        assert stats['snapshot_count'] == 3
        assert stats['total_operations'] == 3


class TestSnapshotManager:
    """Test SnapshotManager orchestration."""
    
    def test_create_auto_snapshot(self):
        """Test auto-snapshot creation via manager."""
        engine = SnapshotEngine()
        manager = SnapshotManager(engine)
        
        draft = create_draft_workspace("draft-001", "sess-001")
        
        snapshot = manager.create_auto_snapshot(
            draft_id="draft-001",
            operation="test",
            user_action="Test auto snapshot",
            draft_workspace=draft,
        )
        
        assert snapshot['snapshot_id'] is not None
        assert snapshot['operation'] == "test"
    
    def test_undo_last_operation(self):
        """Test undo via manager."""
        engine = SnapshotEngine()
        manager = SnapshotManager(engine)
        
        draft = create_draft_workspace("draft-001", "sess-001")
        
        # Create 2 snapshots
        manager.create_auto_snapshot(
            draft_id="draft-001",
            operation="op1",
            user_action="Op 1",
            draft_workspace=draft,
        )
        
        manager.create_auto_snapshot(
            draft_id="draft-001",
            operation="op2",
            user_action="Op 2",
            draft_workspace=draft,
        )
        
        # Undo
        result = manager.undo_last_operation(draft)
        
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
