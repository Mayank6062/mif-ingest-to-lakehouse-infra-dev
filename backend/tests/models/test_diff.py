"""
Unit tests for Diff Engine.

Tests:
- File diff computation
- Changeset creation
- Statistics calculation
- Conflict detection (placeholder)
"""

import pytest
from app.models.diff import (
    DiffType,
    DiffEngine,
    FileDiff,
    GlueJobDiff,
    ChangeSet,
)
from app.models.state_v2 import DraftFile, GlueJobEntry
from datetime import datetime


class TestDiffType:
    """Test DiffType enum."""
    
    def test_diff_types(self):
        """Test DiffType values."""
        assert DiffType.ADDED == "added"
        assert DiffType.MODIFIED == "modified"
        assert DiffType.DELETED == "deleted"
        assert DiffType.RENAMED == "renamed"
        assert DiffType.UNCHANGED == "unchanged"


class TestFileDiff:
    """Test FileDiff computation."""
    
    def test_compute_file_diff_added(self):
        """Test computing diff for added file."""
        old_content = None
        new_content = "resource 'aws_s3_bucket' 'test' {}"
        
        diff = DiffEngine.compute_file_diff(
            old_content=old_content,
            new_content=new_content,
            file_path="saptcc/main.tf",
        )
        
        assert diff['diff_type'] == DiffType.ADDED
        assert diff['file_path'] == "saptcc/main.tf"
        assert diff['lines_added'] == 1
        assert diff['lines_removed'] == 0
    
    def test_compute_file_diff_modified(self):
        """Test computing diff for modified file."""
        old_content = "local {\n  name = 'old'\n}"
        new_content = "local {\n  name = 'new'\n  tag = 'v1'\n}"
        
        diff = DiffEngine.compute_file_diff(
            old_content=old_content,
            new_content=new_content,
            file_path="saptcc/locals.tf",
        )
        
        assert diff['diff_type'] == DiffType.MODIFIED
        assert diff['lines_added'] >= 1
        assert diff['lines_removed'] >= 0
    
    def test_compute_file_diff_deleted(self):
        """Test computing diff for deleted file."""
        old_content = "resource 'aws_s3_bucket' 'test' {}"
        new_content = None
        
        diff = DiffEngine.compute_file_diff(
            old_content=old_content,
            new_content=new_content,
            file_path="saptcc/deleted.tf",
        )
        
        assert diff['diff_type'] == DiffType.DELETED
        assert diff['lines_removed'] == 1


class TestChangeSet:
    """Test ChangeSet computation."""
    
    def test_compute_changeset_single_file_added(self):
        """Test changeset with single file added."""
        changeset = DiffEngine.compute_changeset(
            changeset_id="cs-001",
            from_snapshot_id="snap-1",
            to_snapshot_id="snap-2",
            old_files=[],
            new_files=[
                {
                    'file_id': 'f1',
                    'path': 'saptcc/locals.tf',
                    'content': 'locals {}',
                }
            ],
            old_jobs=[],
            new_jobs=[],
        )
        
        assert changeset['changeset_id'] == 'cs-001'
        assert changeset['files_added'] == 1
        assert changeset['files_modified'] == 0
        assert changeset['files_deleted'] == 0
        assert len(changeset['file_diffs']) == 1
    
    def test_compute_changeset_multiple_changes(self):
        """Test changeset with multiple file changes."""
        old_files = [
            {
                'file_id': 'f1',
                'path': 'saptcc/locals.tf',
                'content': 'locals { }',
            }
        ]
        
        new_files = [
            {
                'file_id': 'f1',
                'path': 'saptcc/locals.tf',
                'content': 'locals { name = "test" }',
            },
            {
                'file_id': 'f2',
                'path': 'saptcc/main.tf',
                'content': 'resource "..." { }',
            }
        ]
        
        changeset = DiffEngine.compute_changeset(
            changeset_id="cs-002",
            from_snapshot_id="snap-1",
            to_snapshot_id="snap-2",
            old_files=old_files,
            new_files=new_files,
            old_jobs=[],
            new_jobs=[],
        )
        
        assert changeset['files_added'] == 1
        assert changeset['files_modified'] == 1
        assert changeset['total_changes'] == 2
    
    def test_compute_changeset_with_jobs(self):
        """Test changeset with glue job additions."""
        old_jobs = []
        
        new_jobs = [
            {
                'job_id': 'job-001',
                'job_key': 'kafka-to-iceberg-batch-saptcc-multi-1',
                'source_system': 'saptcc',
                'schema_grain': 'multi-1',
                'topic': 'dev.saptcc.multi-1.raw',
                'environment': 'dev',
                'created_at': datetime.now(),
                'order_in_draft': 1,
            }
        ]
        
        changeset = DiffEngine.compute_changeset(
            changeset_id="cs-003",
            from_snapshot_id="snap-1",
            to_snapshot_id="snap-2",
            old_files=[],
            new_files=[],
            old_jobs=old_jobs,
            new_jobs=new_jobs,
        )
        
        assert changeset['jobs_added'] == 1
        assert len(changeset['job_diffs']) == 1


class TestDiffStatistics:
    """Test changeset statistics."""
    
    def test_compute_statistics(self):
        """Test computing statistics from changeset."""
        changeset: ChangeSet = {
            'changeset_id': 'cs-001',
            'from_snapshot_id': 'snap-1',
            'to_snapshot_id': 'snap-2',
            'file_diffs': [
                {
                    'file_path': 'f1.tf',
                    'diff_type': DiffType.ADDED,
                    'old_content': None,
                    'new_content': 'content',
                    'size_before': 0,
                    'size_after': 7,
                    'lines_added': 1,
                    'lines_removed': 0,
                }
            ],
            'job_diffs': [],
            'files_added': 1,
            'files_modified': 0,
            'files_deleted': 0,
            'jobs_added': 0,
            'jobs_modified': 0,
            'jobs_deleted': 0,
            'total_changes': 1,
            'summary': '1 file added',
        }
        
        stats = DiffEngine.compute_statistics(changeset)
        
        assert stats['files_changed'] == 1
        assert stats['lines_added'] == 1
        assert stats['lines_removed'] == 0
        assert stats['total_lines_changed'] == 1


class TestConflictDetection:
    """Test conflict detection (placeholder)."""
    
    def test_detect_conflicts_no_conflicts(self):
        """Test conflict detection when there are none."""
        changeset: ChangeSet = {
            'changeset_id': 'cs-001',
            'from_snapshot_id': 'snap-1',
            'to_snapshot_id': 'snap-2',
            'file_diffs': [],
            'job_diffs': [],
            'files_added': 0,
            'files_modified': 0,
            'files_deleted': 0,
            'jobs_added': 0,
            'jobs_modified': 0,
            'jobs_deleted': 0,
            'total_changes': 0,
            'summary': 'No changes',
        }
        
        conflicts = DiffEngine.detect_conflicts(changeset)
        
        # Should be empty or placeholder
        assert isinstance(conflicts, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
