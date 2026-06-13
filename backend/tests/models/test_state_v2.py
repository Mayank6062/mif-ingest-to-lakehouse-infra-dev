"""
Unit tests for State Model V2.

Tests:
- Model creation and validation
- Default values
- Enum values
- Helper function correctness
"""

import pytest
from datetime import datetime
from app.models.state_v2 import (
    Session,
    DraftWorkspace,
    DraftFile,
    GlueJobEntry,
    ValidationReport,
    Snapshot,
    Message,
    ActionCard,
    SessionStatus,
    DraftWorkspaceStatus,
    create_session,
    create_draft_workspace,
    create_message,
    create_validation_report,
    create_snapshot,
)


class TestSessionModel:
    """Test Session entity creation and fields."""
    
    def test_create_session(self):
        """Test creating a session."""
        session = create_session(
            session_id="sess-001",
            user_email="test@example.com",
            environment="dev",
            repository_url="https://github.com/example/repo",
            base_branch="main",
        )
        
        assert session['session_id'] == "sess-001"
        assert session['user_email'] == "test@example.com"
        assert session['environment'] == "dev"
        assert session['status'] == SessionStatus.ACTIVE
        assert session['message_history'] == []
        assert session['current_draft_id'] is None
        assert session['created_at'] is not None
        assert isinstance(session['created_at'], datetime)
    
    def test_session_status_enum(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.PAUSED == "paused"
        assert SessionStatus.CLOSED == "closed"
        assert SessionStatus.PR_CREATED == "pr_created"
        assert SessionStatus.ARCHIVED == "archived"


class TestDraftWorkspaceModel:
    """Test DraftWorkspace entity creation and fields."""
    
    def test_create_draft_workspace(self):
        """Test creating a draft workspace."""
        draft = create_draft_workspace("draft-001", "sess-001")
        
        assert draft['draft_id'] == "draft-001"
        assert draft['session_id'] == "sess-001"
        assert draft['status'] == DraftWorkspaceStatus.OPEN
        assert draft['files'] == []
        assert draft['glue_jobs'] == []
        assert draft['validation_reports'] == []
        assert draft['snapshot_refs'] == []
        assert draft['current_snapshot_index'] == 0
        assert draft['updated_at'] is not None
    
    def test_draft_workspace_status_enum(self):
        """Test DraftWorkspaceStatus enum values."""
        assert DraftWorkspaceStatus.OPEN == "open"
        assert DraftWorkspaceStatus.VALIDATED == "validated"
        assert DraftWorkspaceStatus.READY_FOR_PR == "ready_for_pr"
        assert DraftWorkspaceStatus.MERGED == "merged"
        assert DraftWorkspaceStatus.ABANDONED == "abandoned"


class TestMessageModel:
    """Test Message entity creation."""
    
    def test_create_message(self):
        """Test creating a message."""
        message = create_message(
            message_id="msg-001",
            role="assistant",
            content="Hello, user!",
            step_name="collect_topic",
        )
        
        assert message['message_id'] == "msg-001"
        assert message['role'] == "assistant"
        assert message['content'] == "Hello, user!"
        assert message['step_name'] == "collect_topic"
        assert message['timestamp'] is not None
        assert message['actions'] == []
    
    def test_message_with_actions(self):
        """Test creating a message with action cards."""
        action: ActionCard = {
            'card_id': 'action-001',
            'card_type': 'approval',
            'message': 'Approve changes?',
        }
        
        message = create_message(
            message_id="msg-002",
            role="assistant",
            content="Do you approve?",
            actions=[action],
        )
        
        assert len(message['actions']) == 1
        assert message['actions'][0]['card_id'] == 'action-001'


class TestValidationReportModel:
    """Test ValidationReport entity creation."""
    
    def test_create_validation_report(self):
        """Test creating a validation report."""
        report = create_validation_report("report-001", "draft-001")
        
        assert report['report_id'] == "report-001"
        assert report['draft_id'] == "draft-001"
        assert report['status'] == "pending"
        assert report['findings'] == []
        assert report['timestamp'] is not None


class TestSnapshotModel:
    """Test Snapshot entity creation."""
    
    def test_create_snapshot(self):
        """Test creating a snapshot."""
        files = [
            {
                'file_id': 'f1',
                'path': 'saptcc/locals.tf',
                'content': 'locals { }',
            }
        ]
        jobs = []
        reports = []
        
        snapshot = create_snapshot(
            snapshot_id="snap-001",
            draft_id="draft-001",
            operation="create_job",
            user_action="Created Glue job",
            files=files,
            glue_jobs=jobs,
            validation_reports=reports,
        )
        
        assert snapshot['snapshot_id'] == "snap-001"
        assert snapshot['draft_id'] == "draft-001"
        assert snapshot['operation'] == "create_job"
        assert snapshot['timestamp'] is not None
        assert len(snapshot['files']) == 1
        assert snapshot['files'][0]['path'] == 'saptcc/locals.tf'


class TestDraftFileModel:
    """Test DraftFile entity."""
    
    def test_draft_file_creation(self):
        """Test creating a draft file."""
        file: DraftFile = {
            'file_id': 'f1',
            'draft_id': 'draft-001',
            'path': 'saptcc/locals.tf',
            'content': 'locals { job_name = "test" }',
            'file_type': 'terraform',
            'mtime': datetime.now(),
            'editable': True,
            'locked_by': None,
            'locked_at': None,
        }
        
        assert file['path'] == 'saptcc/locals.tf'
        assert file['file_type'] == 'terraform'
        assert file['editable'] is True


class TestGlueJobEntryModel:
    """Test GlueJobEntry entity."""
    
    def test_glue_job_entry_creation(self):
        """Test creating a glue job entry."""
        job: GlueJobEntry = {
            'job_id': 'job-001',
            'job_key': 'kafka-to-iceberg-batch-saptcc-multi-1',
            'source_system': 'saptcc',
            'schema_grain': 'multi-1',
            'topic': 'dev.saptcc.multi-1.raw',
            'environment': 'dev',
            'created_at': datetime.now(),
            'order_in_draft': 1,
        }
        
        assert job['job_key'] == 'kafka-to-iceberg-batch-saptcc-multi-1'
        assert job['source_system'] == 'saptcc'
        assert job['schema_grain'] == 'multi-1'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
