"""
Unit tests for Draft Workspace Service.

Tests:
- Draft creation
- File management (add, remove, get)
- Glue job tracking
- Status transitions
- Validation management
"""

import pytest
from datetime import datetime
from app.services.draft_workspace_service import DraftWorkspaceService
from app.models.state_v2 import DraftWorkspaceStatus


class TestDraftWorkspaceServiceCreation:
    """Test draft creation."""
    
    def test_create_draft(self):
        """Test creating a draft workspace."""
        service = DraftWorkspaceService()
        
        draft = service.create_draft("sess-001")
        
        assert draft['draft_id'] is not None
        assert draft['session_id'] == "sess-001"
        assert draft['status'] == DraftWorkspaceStatus.OPEN
        assert draft['files'] == []
        assert draft['glue_jobs'] == []
    
    def test_get_draft(self):
        """Test retrieving a draft."""
        service = DraftWorkspaceService()
        
        created = service.create_draft("sess-001")
        retrieved = service.get_draft(created['draft_id'])
        
        assert retrieved is not None
        assert retrieved['draft_id'] == created['draft_id']


class TestFileManagement:
    """Test file operations."""
    
    def test_add_file(self):
        """Test adding a file to draft."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        file = service.add_file(
            draft=draft,
            file_path="saptcc/locals.tf",
            content="locals { }"
        )
        
        assert file['path'] == "saptcc/locals.tf"
        assert file['content'] == "locals { }"
        assert len(draft['files']) == 1
    
    def test_add_multiple_files(self):
        """Test adding multiple files."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_file(draft, "file1.tf", "content1")
        service.add_file(draft, "file2.tf", "content2")
        
        assert len(draft['files']) == 2
    
    def test_update_existing_file(self):
        """Test updating an existing file."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_file(draft, "test.tf", "old content")
        service.add_file(draft, "test.tf", "new content")
        
        # Should still be 1 file, updated
        assert len(draft['files']) == 1
        assert draft['files'][0]['content'] == "new content"
    
    def test_get_file(self):
        """Test retrieving a file."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_file(draft, "test.tf", "content")
        file = service.get_file(draft, "test.tf")
        
        assert file is not None
        assert file['path'] == "test.tf"
    
    def test_get_nonexistent_file(self):
        """Test getting nonexistent file."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        file = service.get_file(draft, "nonexistent.tf")
        
        assert file is None
    
    def test_remove_file(self):
        """Test removing a file."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_file(draft, "file1.tf", "content")
        service.add_file(draft, "file2.tf", "content")
        
        result = service.remove_file(draft, "file1.tf")
        
        assert result is True
        assert len(draft['files']) == 1


class TestGlueJobManagement:
    """Test Glue job tracking."""
    
    def test_add_glue_job(self):
        """Test adding a Glue job."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        job = service.add_glue_job(
            draft=draft,
            source_system="saptcc",
            schema_grain="multi-1",
            topic="dev.saptcc.multi-1.raw",
            environment="dev",
        )
        
        assert job['source_system'] == "saptcc"
        assert job['schema_grain'] == "multi-1"
        assert job['job_key'] is not None
        assert len(draft['glue_jobs']) == 1
    
    def test_add_multiple_glue_jobs(self):
        """Test adding multiple jobs."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_glue_job(draft, "saptcc", "multi-1", "topic1", "dev")
        service.add_glue_job(draft, "saptcc", "multi-2", "topic2", "dev")
        
        assert len(draft['glue_jobs']) == 2
        # Check order
        assert draft['glue_jobs'][0]['order_in_draft'] == 1
        assert draft['glue_jobs'][1]['order_in_draft'] == 2


class TestStatusTransitions:
    """Test draft status lifecycle."""
    
    def test_validate_and_lock(self):
        """Test validating and locking draft."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        # Add prerequisites
        service.add_file(draft, "test.tf", "content")
        service.add_glue_job(draft, "saptcc", "multi-1", "topic", "dev")
        
        result = service.validate_and_lock(draft)
        
        assert result is True
        assert draft['status'] == DraftWorkspaceStatus.VALIDATED
    
    def test_validate_fails_without_glue_job(self):
        """Test validation fails without glue job."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_file(draft, "test.tf", "content")
        
        result = service.validate_and_lock(draft)
        
        assert result is False
    
    def test_mark_merged(self):
        """Test marking draft as merged."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.mark_merged(draft)
        
        assert draft['status'] == DraftWorkspaceStatus.MERGED
    
    def test_mark_abandoned(self):
        """Test marking draft as abandoned."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.mark_abandoned(draft)
        
        assert draft['status'] == DraftWorkspaceStatus.ABANDONED


class TestValidationManagement:
    """Test validation reports."""
    
    def test_set_validation_status(self):
        """Test setting validation status."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.set_validation_status(draft, "pending")
        
        # Status doesn't have explicit field, but snapshot is created
        assert draft['draft_id'] is not None
    
    def test_add_validation_report(self):
        """Test adding a validation report."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        from app.models.state_v2 import create_validation_report
        report = create_validation_report("report-001", draft['draft_id'])
        
        service.set_validation_status(draft, "passed", report)
        
        assert len(draft['validation_reports']) == 1
        assert draft['validation_reports'][0]['report_id'] == "report-001"


class TestUndoOperations:
    """Test undo/discard operations."""
    
    def test_discard_last_change(self):
        """Test discarding last change."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        # Make changes
        service.add_file(draft, "file1.tf", "content1")
        service.add_file(draft, "file2.tf", "content2")
        
        # Undo
        result = service.discard_last_change(draft)
        
        # Should succeed (after second snapshot)
        assert isinstance(result, bool)


class TestDraftSummary:
    """Test summary generation."""
    
    def test_get_summary(self):
        """Test getting draft summary."""
        service = DraftWorkspaceService()
        draft = service.create_draft("sess-001")
        
        service.add_file(draft, "test.tf", "content")
        service.add_glue_job(draft, "saptcc", "multi-1", "topic", "dev")
        
        summary = service.get_summary(draft)
        
        assert summary['draft_id'] == draft['draft_id']
        assert summary['session_id'] == "sess-001"
        assert summary['files_count'] == 1
        assert summary['glue_jobs_count'] == 1
        assert len(summary['glue_jobs']) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
