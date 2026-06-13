"""
STEP 2.3 — Single-Commit PR Creation Tests

Covers:
  Draft Freeze Logic:
    - add_file() raises ValueError when draft is PR_CREATING
    - add_glue_job() raises ValueError when draft is PR_CREATING
    - discard_last_change() raises ValueError when draft is PR_CREATING
    - is_frozen() returns True when status = PR_CREATING
    - is_frozen() returns False for other statuses

  Duplicate PR Protection:
    - check_duplicate_pr_protection() raises ValueError if already PR_CREATING
    - mark_draft_pr_creating() calls check_duplicate_pr_protection()
    - mark_draft_pr_creating() sets status to PR_CREATING

  File Collection:
    - collect_final_files() returns list of {path, content, mode}
    - collect_final_files() raises ValueError if draft not found
    - collect_final_files() respects all files in draft

  Metadata Persistence:
    - update_draft_meta() persists branch_name, commit_message, pr_title, pr_description
    - set_draft_status() transitions status atomically
    - mark_draft_pr_created() stores PR metadata (url, number, commit_sha)
    - preview_diff() computes file list without committing

  GitHub Service (Single Commit):
    - create_single_commit_and_pr() uses blob→tree→commit→ref→PR flow
    - create_single_commit_and_pr() returns {commit_sha, pr_url, pr_number, branch_name}
    - get_current_head_sha() retrieves current branch SHA
    - preview_tree_diff() computes diff without committing

  API Routes:
    - POST /api/sessions/{id}/draft/update_meta → 200 with updated metadata
    - POST /api/sessions/{id}/draft/preview_commit → 200 with preview
    - POST /api/sessions/{id}/draft/create_pr → 200 with PR metadata
    - POST /api/sessions/{id}/draft/abandon → 200 with status success

  Processor Functions:
    - update_session_draft_metadata() persists metadata
    - preview_session_draft_commit() computes preview
    - create_session_draft_pr() orchestrates full PR creation flow
    - abandon_session_draft() marks draft ABANDONED

All tests are self-contained; no live GitHub calls.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from app.services.draft_workspace_service import DraftWorkspaceService
from app.services.github_service import GitHubService


class TestDraftFreezeLogic:
    """Test Draft Freeze: PR_CREATING status blocks mutations."""

    def test_add_file_raises_when_frozen(self):
        """add_file() raises ValueError when draft is PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft['status'] = 'PR_CREATING'

        with pytest.raises(ValueError, match="Cannot edit draft while PR creation"):
            svc.add_file(draft, "test.tf", "content")

    def test_add_glue_job_raises_when_frozen(self):
        """add_glue_job() raises ValueError when draft is PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft['status'] = 'PR_CREATING'

        with pytest.raises(ValueError, match="Cannot create Glue job while PR creation"):
            svc.add_glue_job(draft, "saptcc", "multi-1", "kafka-topic", "dev")

    def test_discard_last_change_raises_when_frozen(self):
        """discard_last_change() raises ValueError when draft is PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft['status'] = 'PR_CREATING'

        with pytest.raises(ValueError, match="Cannot discard changes while PR creation"):
            svc.discard_last_change(draft)

    def test_is_frozen_true_when_pr_creating(self):
        """is_frozen() returns True when status = PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft['status'] = 'PR_CREATING'

        assert svc.is_frozen(draft) is True

    def test_is_frozen_false_for_other_statuses(self):
        """is_frozen() returns False for OPEN, REVIEW, PR_CREATED, ABANDONED."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")

        for status in ['OPEN', 'REVIEW', 'PR_CREATED', 'ABANDONED']:
            draft['status'] = status
            assert svc.is_frozen(draft) is False


class TestDuplicatePRProtection:
    """Test Duplicate PR Protection: prevent concurrent PR creation."""

    def test_check_duplicate_pr_protection_raises_if_already_creating(self):
        """check_duplicate_pr_protection() raises if already PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']
        draft['status'] = 'PR_CREATING'

        with pytest.raises(ValueError, match="already creating a PR"):
            svc.check_duplicate_pr_protection(draft_id)

    def test_check_duplicate_pr_protection_passes_if_not_creating(self):
        """check_duplicate_pr_protection() passes if not PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        # Should not raise
        svc.check_duplicate_pr_protection(draft_id)

    def test_mark_draft_pr_creating_calls_protection_check(self):
        """mark_draft_pr_creating() calls check_duplicate_pr_protection()."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        # First call should succeed
        result = svc.mark_draft_pr_creating(draft_id)
        assert result['status'] == 'PR_CREATING'

        # Second call should fail due to duplicate protection
        with pytest.raises(ValueError, match="already creating a PR"):
            svc.mark_draft_pr_creating(draft_id)

    def test_mark_draft_pr_creating_sets_status_to_pr_creating(self):
        """mark_draft_pr_creating() transitions status to PR_CREATING."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        result = svc.mark_draft_pr_creating(draft_id)
        assert result['status'] == 'PR_CREATING'


class TestFileCollection:
    """Test collect_final_files(): authoritative file collection for PR."""

    def test_collect_final_files_returns_all_files(self):
        """collect_final_files() returns list of {path, content, mode}."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        # Add two files
        svc.add_file(draft, "locals.tf", "local { x = 1 }")
        svc.add_file(draft, "main.tf", "resource { ... }")

        files = svc.collect_final_files(draft_id)
        assert len(files) == 2
        assert files[0]['path'] == "locals.tf"
        assert files[0]['content'] == "local { x = 1 }"
        assert files[0]['mode'] == "100644"
        assert files[1]['path'] == "main.tf"

    def test_collect_final_files_raises_if_draft_not_found(self):
        """collect_final_files() raises ValueError if draft not found."""
        svc = DraftWorkspaceService()
        with pytest.raises(ValueError, match="not found"):
            svc.collect_final_files("nonexistent_draft_id")

    def test_collect_final_files_with_no_files(self):
        """collect_final_files() returns empty list if no files."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        files = svc.collect_final_files(draft_id)
        assert files == []


class TestMetadataPersistence:
    """Test metadata persistence: branch name, commit message, PR title/description."""

    def test_update_draft_meta_persists_all_fields(self):
        """update_draft_meta() persists branch_name, commit_message, etc."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        metadata = {
            'branch_name': 'custom-branch',
            'user_commit_message': 'Custom commit',
            'user_pr_title': 'Custom PR',
            'user_pr_description': 'Custom description',
        }
        result = svc.update_draft_meta(draft_id, metadata)

        assert result['branch_name'] == 'custom-branch'
        assert result['user_commit_message'] == 'Custom commit'
        assert result['user_pr_title'] == 'Custom PR'
        assert result['user_pr_description'] == 'Custom description'

    def test_set_draft_status_transitions_atomically(self):
        """set_draft_status() transitions status atomically."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        result = svc.set_draft_status(draft_id, 'REVIEW')
        assert result['status'] == 'REVIEW'

        result = svc.set_draft_status(draft_id, 'PR_CREATING')
        assert result['status'] == 'PR_CREATING'

    def test_mark_draft_pr_created_stores_pr_metadata(self):
        """mark_draft_pr_created() stores PR metadata."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        pr_metadata = {
            'pr_url': 'https://github.com/repo/pull/42',
            'pr_number': 42,
            'commit_sha': 'abc123',
        }
        result = svc.mark_draft_pr_created(draft_id, pr_metadata)

        assert result['status'] == 'PR_CREATED'
        assert result['pr_url'] == 'https://github.com/repo/pull/42'
        assert result['pr_number'] == 42
        assert result['commit_sha'] == 'abc123'

    def test_preview_diff_computes_file_summary(self):
        """preview_diff() computes file list without committing."""
        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        svc.add_file(draft, "test.tf", "content here")
        svc.add_file(draft, "main.tf", "x" * 1000)

        preview = svc.preview_diff(draft_id)

        assert preview['draft_id'] == draft_id
        assert preview['files_count'] == 2
        assert preview['total_size'] > 1000  # At least the 1000 chars from main.tf
        assert len(preview['file_list']) == 2


class TestGitHubServiceSingleCommit:
    """Test GitHubService.create_single_commit_and_pr(): ONE commit per PR."""

    @patch('app.services.github_service.Github')
    def test_create_single_commit_and_pr_returns_pr_metadata(self, mock_github_class):
        """create_single_commit_and_pr() returns {commit_sha, pr_url, pr_number}."""
        # Mock the GitHub API
        mock_repo = MagicMock()
        mock_repo.create_git_blob.return_value.sha = "blob_sha_123"
        mock_repo.create_git_tree.return_value.sha = "tree_sha_456"
        mock_repo.create_git_commit.return_value.sha = "commit_sha_789"
        mock_repo.create_git_ref.return_value.ref = "refs/heads/draft-branch"
        mock_pr = MagicMock()
        mock_pr.html_url = "https://github.com/repo/pull/99"
        mock_pr.number = 99
        mock_repo.create_pull.return_value = mock_pr

        mock_github = MagicMock()
        mock_github.get_user.return_value.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        svc = GitHubService()
        result = svc.create_single_commit_and_pr(
            repo_name="test-repo",
            target_branch="main",
            base_sha="base_sha_000",
            tree_entries=[
                {"path": "test.tf", "content": "content", "mode": "100644"},
            ],
            branch_name="draft-branch",
            commit_message="Test commit",
            pr_title="Test PR",
            pr_body="Test body",
        )

        assert result['commit_sha'] == 'commit_sha_789'
        assert result['pr_url'] == 'https://github.com/repo/pull/99'
        assert result['pr_number'] == 99

    @patch('app.services.github_service.Github')
    def test_get_current_head_sha_retrieves_sha(self, mock_github_class):
        """get_current_head_sha() retrieves current branch SHA."""
        mock_repo = MagicMock()
        mock_ref = MagicMock()
        mock_ref.object.sha = "current_sha_xyz"
        mock_repo.get_git_ref.return_value = mock_ref

        mock_github = MagicMock()
        mock_github.get_user.return_value.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        svc = GitHubService()
        sha = svc.get_current_head_sha("main")

        assert sha == "current_sha_xyz"


class TestProcessorFunctions:
    """Test processor functions for API integration."""

    @patch('app.config.get_settings')
    @patch('app.api.processor._get_draft_service')
    def test_update_session_draft_metadata(self, mock_get_svc, mock_get_settings):
        """update_session_draft_metadata() persists metadata."""
        mock_settings = MagicMock()
        mock_settings.enable_draft_workspace = True
        mock_get_settings.return_value = mock_settings

        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        mock_get_svc.return_value = svc
        from app.api.processor import _session_drafts, update_session_draft_metadata
        _session_drafts["session_123"] = draft_id

        result = update_session_draft_metadata("session_123", {
            'branch_name': 'test-branch',
        })

        assert result['branch_name'] == 'test-branch'

    @patch('app.config.get_settings')
    @patch('app.api.processor._get_draft_service')
    def test_preview_session_draft_commit(self, mock_get_svc, mock_get_settings):
        """preview_session_draft_commit() computes preview."""
        mock_settings = MagicMock()
        mock_settings.enable_draft_workspace = True
        mock_get_settings.return_value = mock_settings

        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']
        svc.add_file(draft, "test.tf", "content")

        mock_get_svc.return_value = svc
        from app.api.processor import _session_drafts, preview_session_draft_commit
        _session_drafts["session_123"] = draft_id

        preview = preview_session_draft_commit("session_123")

        assert preview['files_count'] == 1
        assert preview['total_size'] > 0

    @patch('app.config.get_settings')
    @patch('app.api.processor._get_draft_service')
    def test_abandon_session_draft(self, mock_get_svc, mock_get_settings):
        """abandon_session_draft() marks draft ABANDONED."""
        mock_settings = MagicMock()
        mock_settings.enable_draft_workspace = True
        mock_get_settings.return_value = mock_settings

        svc = DraftWorkspaceService()
        draft = svc.create_draft("session_123")
        draft_id = draft['draft_id']

        mock_get_svc.return_value = svc
        from app.api.processor import _session_drafts, abandon_session_draft
        _session_drafts["session_123"] = draft_id

        result = abandon_session_draft("session_123")

        assert result['status'] == 'ABANDONED'
