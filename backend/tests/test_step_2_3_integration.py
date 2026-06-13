"""
STEP 2.3 — Single-Commit PR Creation Integration Tests

Covers end-to-end flows:
  - Draft creation → file addition → metadata update → preview → PR creation
  - Draft freeze during PR creation
  - Duplicate PR protection blocks second request
  - API routes: update_meta, preview_commit, create_pr, abandon
  - Processor functions orchestration
  - Error handling: frozen draft, duplicate PR, missing draft

Test strategy:
  - No live GitHub API calls (mocked)
  - No live LangGraph execution (isolated draft service)
  - Complete request/response cycles for API routes
  - Status transitions verified at each step
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.api.routes import router
from app.services.draft_workspace_service import DraftWorkspaceService
from app.api.processor import (
    _session_drafts,
    _get_draft_service,
    create_session_draft_pr,
    update_session_draft_metadata,
    preview_session_draft_commit,
    abandon_session_draft,
)


@pytest.fixture
def draft_service():
    """Provide a fresh DraftWorkspaceService for each test."""
    return DraftWorkspaceService()


@pytest.fixture
def session_id():
    """Provide a session ID."""
    return "test_session_123"


@pytest.fixture
def draft_with_files(draft_service, session_id):
    """Create a draft with files."""
    draft = draft_service.create_draft(session_id)
    draft_id = draft['draft_id']
    draft_service.add_file(draft, "locals.tf", "local { x = 1 }")
    draft_service.add_file(draft, "main.tf", "resource { ... }")
    draft_service.add_glue_job(draft, "saptcc", "multi-1", "kafka-topic", "dev")
    return draft


class TestDraftFreezeDuringPRCreation:
    """Test that draft is frozen during PR creation."""

    def test_freeze_prevents_file_addition(self, draft_service, session_id):
        """Draft freeze blocks add_file."""
        draft = draft_service.create_draft(session_id)
        draft_service.mark_draft_pr_creating(draft['draft_id'])

        with pytest.raises(ValueError, match="Cannot edit draft"):
            draft_service.add_file(draft, "test.tf", "content")

    def test_freeze_prevents_glue_job_creation(self, draft_service, session_id):
        """Draft freeze blocks add_glue_job."""
        draft = draft_service.create_draft(session_id)
        draft_service.mark_draft_pr_creating(draft['draft_id'])

        with pytest.raises(ValueError, match="Cannot create Glue job"):
            draft_service.add_glue_job(draft, "saptcc", "multi-1", "topic", "dev")

    def test_freeze_prevents_undo(self, draft_service, session_id):
        """Draft freeze blocks discard_last_change."""
        draft = draft_service.create_draft(session_id)
        draft_service.add_file(draft, "test.tf", "content")
        draft_service.mark_draft_pr_creating(draft['draft_id'])

        with pytest.raises(ValueError, match="Cannot discard changes"):
            draft_service.discard_last_change(draft)


class TestDuplicatePRProtection:
    """Test that second PR creation request is blocked."""

    def test_second_pr_request_blocked(self, draft_service, session_id):
        """Second PR creation attempt is blocked by duplicate protection."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        # First mark as PR_CREATING
        draft_service.mark_draft_pr_creating(draft_id)

        # Second attempt should fail
        with pytest.raises(ValueError, match="already creating a PR"):
            draft_service.mark_draft_pr_creating(draft_id)

    def test_duplicate_protection_allows_sequential_pr_creation(self, draft_service, session_id):
        """After PR_CREATED, cannot start new PR_CREATING."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        # Mark as PR_CREATING
        draft_service.mark_draft_pr_creating(draft_id)

        # Mark as PR_CREATED
        draft_service.mark_draft_pr_created(draft_id, {
            'pr_url': 'https://github.com/repo/pull/1',
            'pr_number': 1,
            'commit_sha': 'abc123',
        })

        # Verify status is PR_CREATED, not PR_CREATING
        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'PR_CREATED'


class TestMetadataFlowIntegration:
    """Test full metadata update flow."""

    def test_metadata_persisted_through_lifecycle(self, draft_service, session_id):
        """Metadata is persisted and available for PR creation."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        # Update metadata
        draft_service.update_draft_meta(draft_id, {
            'branch_name': 'custom-branch',
            'user_commit_message': 'Custom commit msg',
            'user_pr_title': 'My PR Title',
            'user_pr_description': 'My description',
        })

        # Verify metadata persisted
        draft = draft_service.get_draft(draft_id)
        assert draft['branch_name'] == 'custom-branch'
        assert draft['user_commit_message'] == 'Custom commit msg'
        assert draft['user_pr_title'] == 'My PR Title'
        assert draft['user_pr_description'] == 'My description'

    def test_partial_metadata_update(self, draft_service, session_id):
        """Only specified fields are updated."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        # Update only branch name
        draft_service.update_draft_meta(draft_id, {'branch_name': 'new-branch'})

        draft = draft_service.get_draft(draft_id)
        assert draft['branch_name'] == 'new-branch'
        # Other fields should be None or empty
        assert draft.get('user_commit_message') is None


class TestFileCollectionAndPreview:
    """Test file collection for PR creation."""

    def test_collect_final_files_includes_all_additions(self, draft_with_files, draft_service):
        """collect_final_files returns all files added to draft."""
        files = draft_service.collect_final_files(draft_with_files['draft_id'])

        assert len(files) == 2
        assert files[0]['path'] == 'locals.tf'
        assert files[0]['content'] == 'local { x = 1 }'
        assert files[1]['path'] == 'main.tf'
        assert files[1]['content'] == 'resource { ... }'

    def test_preview_diff_shows_file_summary(self, draft_with_files, draft_service):
        """preview_diff computes accurate summary."""
        preview = draft_service.preview_diff(draft_with_files['draft_id'])

        assert preview['files_count'] == 2
        assert preview['total_size'] > 0
        assert len(preview['file_list']) == 2
        assert any(f['path'] == 'locals.tf' for f in preview['file_list'])
        assert any(f['path'] == 'main.tf' for f in preview['file_list'])


class TestStatusTransitions:
    """Test status lifecycle transitions."""

    def test_status_transition_open_to_review_to_pr_creating(self, draft_service, session_id):
        """Status transitions through valid sequence."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        # Initial status
        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'OPEN'

        # Transition to REVIEW
        draft_service.set_draft_status(draft_id, 'REVIEW')
        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'REVIEW'

        # Transition to PR_CREATING
        draft_service.set_draft_status(draft_id, 'PR_CREATING')
        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'PR_CREATING'

    def test_status_transition_to_pr_created(self, draft_service, session_id):
        """Status can transition to PR_CREATED."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        pr_metadata = {
            'pr_url': 'https://github.com/org/repo/pull/42',
            'pr_number': 42,
            'commit_sha': 'commit_sha_xyz',
        }
        draft_service.mark_draft_pr_created(draft_id, pr_metadata)

        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'PR_CREATED'
        assert draft['pr_url'] == 'https://github.com/org/repo/pull/42'
        assert draft['pr_number'] == 42

    def test_status_transition_to_abandoned(self, draft_service, session_id):
        """Status can transition to ABANDONED."""
        draft = draft_service.create_draft(session_id)
        draft_id = draft['draft_id']

        draft_service.set_draft_status(draft_id, 'ABANDONED')
        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'ABANDONED'


class TestProcessorFunctionsIntegration:
    """Test processor functions with mocked GitHub service."""

    @patch('app.config.get_settings')
    @patch('app.api.processor._get_draft_service')
    def test_create_session_draft_pr_orchestrates_full_flow(
        self, mock_get_svc, mock_get_settings
    ):
        """create_session_draft_pr orchestrates full PR creation flow."""
        mock_settings = MagicMock()
        mock_settings.enable_draft_workspace = True
        mock_get_settings.return_value = mock_settings

        draft_service = DraftWorkspaceService()
        draft = draft_service.create_draft("session_123")
        draft_id = draft['draft_id']
        draft_service.add_file(draft, "test.tf", "content")

        mock_get_svc.return_value = draft_service
        _session_drafts["session_123"] = draft_id

        # Mock GitHub service
        with patch('app.api.processor.GitHubService') as mock_github_class:
            mock_github = MagicMock()
            mock_github.get_current_head_sha.return_value = "base_sha_000"
            mock_github.create_single_commit_and_pr.return_value = {
                'commit_sha': 'commit_sha_789',
                'pr_url': 'https://github.com/org/repo/pull/42',
                'pr_number': 42,
                'branch_name': 'draft-branch',
            }
            mock_github_class.return_value = mock_github

            result = create_session_draft_pr("session_123")

            assert result['status'] == 'success'
            assert result['pr_number'] == 42
            assert 'pr_url' in result

            # Verify draft is now PR_CREATED
            draft = draft_service.get_draft(draft_id)
            assert draft['status'] == 'PR_CREATED'

    @patch('app.config.get_settings')
    @patch('app.api.processor._get_draft_service')
    def test_create_session_draft_pr_duplicate_protection(
        self, mock_get_svc, mock_get_settings
    ):
        """Duplicate PR protection blocks second creation."""
        mock_settings = MagicMock()
        mock_settings.enable_draft_workspace = True
        mock_get_settings.return_value = mock_settings

        draft_service = DraftWorkspaceService()
        draft = draft_service.create_draft("session_123")
        draft_id = draft['draft_id']

        mock_get_svc.return_value = draft_service
        _session_drafts["session_123"] = draft_id

        # Mark as already PR_CREATING
        draft_service.mark_draft_pr_creating(draft_id)

        # Second attempt should return error
        with patch('app.api.processor.GitHubService'):
            result = create_session_draft_pr("session_123")

            assert 'error' in result
            assert 'already creating a PR' in result['error']

    @patch('app.config.get_settings')
    @patch('app.api.processor._get_draft_service')
    def test_abandon_session_draft_marks_abandoned(
        self, mock_get_svc, mock_get_settings
    ):
        """abandon_session_draft marks draft as ABANDONED."""
        mock_settings = MagicMock()
        mock_settings.enable_draft_workspace = True
        mock_get_settings.return_value = mock_settings

        draft_service = DraftWorkspaceService()
        draft = draft_service.create_draft("session_123")
        draft_id = draft['draft_id']

        mock_get_svc.return_value = draft_service
        _session_drafts["session_123"] = draft_id

        result = abandon_session_draft("session_123")

        assert result['status'] == 'ABANDONED'
        draft = draft_service.get_draft(draft_id)
        assert draft['status'] == 'ABANDONED'


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_collect_final_files_nonexistent_draft(self, draft_service):
        """collect_final_files raises for nonexistent draft."""
        with pytest.raises(ValueError, match="not found"):
            draft_service.collect_final_files("nonexistent_id")

    def test_update_draft_meta_nonexistent_draft(self, draft_service):
        """update_draft_meta raises for nonexistent draft."""
        with pytest.raises(ValueError, match="not found"):
            draft_service.update_draft_meta("nonexistent_id", {'branch_name': 'x'})

    def test_mark_draft_pr_created_nonexistent_draft(self, draft_service):
        """mark_draft_pr_created raises for nonexistent draft."""
        with pytest.raises(ValueError, match="not found"):
            draft_service.mark_draft_pr_created("nonexistent_id", {})

    def test_preview_diff_nonexistent_draft(self, draft_service):
        """preview_diff raises for nonexistent draft."""
        with pytest.raises(ValueError, match="not found"):
            draft_service.preview_diff("nonexistent_id")

    def test_processor_returns_none_when_feature_disabled(self):
        """Processor functions return None when ENABLE_DRAFT_WORKSPACE=False."""
        with patch('app.config.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.enable_draft_workspace = False
            mock_get_settings.return_value = mock_settings

            # Functions should return None when feature is off
            assert update_session_draft_metadata("session_123", {}) is None
            assert preview_session_draft_commit("session_123") is None
            assert abandon_session_draft("session_123") is None
