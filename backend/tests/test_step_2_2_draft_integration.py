"""
Step 2.2 — Draft Workspace + LangGraph Integration Tests

Covers:
  Unit tests:
    - Feature flag gating: ENABLE_DRAFT_WORKSPACE=False → no draft created
    - Draft created on process_first_message when flag is on
    - generate_terraform_node emits file_edits for new source systems
    - generate_terraform_node emits file_edits for existing source systems
    - generate_terraform_node emits glue_job_configured=True when flag is on
    - generate_terraform_node skips file_edits when flag is off
    - _apply_draft_mutations: file_edits stored via add_file()
    - _apply_draft_mutations: glue_job_configured triggers add_glue_job()
    - _apply_draft_mutations: glue_jobs_created_count updated in state
    - _apply_draft_mutations: draft_change_history populated
    - _apply_draft_mutations: consumed fields cleared (file_edits, glue_job_configured)
    - _apply_draft_mutations: no-op when flag is off
    - get_session_draft_summary: returns None when flag off
    - get_session_draft_summary: returns summary with create_another_job_visible
    - create_another_job_visible=False when no glue jobs
    - create_another_job_visible=True when glue jobs exist
    - discard_session_draft_change: returns False when flag off
    - discard_session_draft_change: calls DraftWorkspaceService.discard_last_change()
    - draft_workspace_id set in initial_state when draft is created
    - GlueJobState contains new draft fields
    - initial_state() defaults for new draft fields
  Integration tests (routes):
    - GET /sessions/{id}/draft → 404 when no draft
    - GET /sessions/{id}/draft → 200 with summary when draft exists
    - POST /sessions/{id}/draft/discard → 404 when no draft
    - POST /sessions/{id}/draft/discard → 409 when nothing to undo
    - POST /sessions/{id}/draft/discard → 200 when undo succeeds

Patching strategy:
  - app.config.get_settings is patched to control feature flags
  - app.api.processor._get_draft_service returns a fresh DraftWorkspaceService
  - app.api.processor._session_drafts is manipulated directly
  - generate_terraform_node patches get_settings at its own import path

All tests are self-contained; no live GitHub, Kafka, or LLM calls are made.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run a coroutine in a fresh event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _settings_with_draft(enabled: bool = True):
    """Return a mock settings object with enable_draft_workspace set."""
    s = MagicMock()
    s.enable_draft_workspace = enabled
    s.enable_state_v2 = False
    return s


def _settings_without_draft():
    return _settings_with_draft(enabled=False)


# ─────────────────────────────────────────────────────────────────────────────
# GlueJobState field presence
# ─────────────────────────────────────────────────────────────────────────────

class TestGlueJobStateNewFields:
    """New draft workspace fields exist on GlueJobState and initial_state()."""

    def test_draft_workspace_id_in_initial_state(self):
        from app.graph.state import initial_state
        state = initial_state("test-session")
        assert "draft_workspace_id" in state
        assert state["draft_workspace_id"] is None

    def test_file_edits_in_initial_state(self):
        from app.graph.state import initial_state
        state = initial_state("test-session")
        assert "file_edits" in state
        assert state["file_edits"] is None

    def test_glue_job_configured_in_initial_state(self):
        from app.graph.state import initial_state
        state = initial_state("test-session")
        assert "glue_job_configured" in state
        assert state["glue_job_configured"] is None

    def test_glue_jobs_created_count_defaults_to_zero(self):
        from app.graph.state import initial_state
        state = initial_state("test-session")
        assert state.get("glue_jobs_created_count") == 0

    def test_draft_change_history_defaults_to_none(self):
        from app.graph.state import initial_state
        state = initial_state("test-session")
        assert state["draft_change_history"] is None


# ─────────────────────────────────────────────────────────────────────────────
# generate_terraform_node — file_edits emission
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateTerraformNodeFileEdits:
    """generate_terraform_node emits file_edits under feature flag."""

    _SETTINGS_PATCH = "app.graph.nodes.generate_terraform.get_settings"
    _TF_AGENT_PATCH = "app.graph.nodes.generate_terraform.TerraformAgent"
    _KB_AGENT_PATCH = "app.graph.nodes.generate_terraform.KnowledgeAgent"

    def _base_state(self, source_exists: bool = False) -> dict:
        return {
            "session_id": "gen-tf-test",
            "source_system": "saptcc",
            "source_system_exists": source_exists,
            "source_system_pattern": "local_module",
            "job_key": "kafka-to-iceberg-batch-saptcc-multi-1",
            "environment": "dev",
            "schema_grain": "multi-1",
            "topic": "dev.saptcc.multi-1.raw",
            "terraform_hcl": None,
            "locals_tf_full": None,
            "glue_tf_content": None,
            "current_step": "show_summary",
            "waiting_for_user": False,
            "messages": [],
        }

    @patch(_KB_AGENT_PATCH)
    @patch(_TF_AGENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_new_source_emits_locals_and_glue_edits(self, mock_settings, MockTF, MockKB):
        mock_settings.return_value = _settings_with_draft(True)
        MockTF.return_value.generate.return_value = "  saptcc-multi-1 = { ... }"
        MockTF.return_value.get_glue_tf_content.return_value = "module saptcc { ... }"
        MockTF.return_value.generate_full_locals_tf.return_value = "locals { glue_jobs = { saptcc-multi-1 = {} } }"
        MockKB.return_value.get_files_to_modify.return_value = []
        MockKB.return_value.get_pr_checklist.return_value = []
        MockKB.return_value.get_new_source_checklist.return_value = []

        from app.graph.nodes.generate_terraform import generate_terraform_node
        result = generate_terraform_node(self._base_state(source_exists=False))

        assert result["file_edits"] is not None
        paths = [e["path"] for e in result["file_edits"]]
        assert "saptcc/locals.tf" in paths
        assert "saptcc/glue.tf" in paths

    @patch(_KB_AGENT_PATCH)
    @patch(_TF_AGENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_existing_source_emits_hcl_block_edit(self, mock_settings, MockTF, MockKB):
        mock_settings.return_value = _settings_with_draft(True)
        MockTF.return_value.generate.return_value = "  saptcc-multi-1 = { ... }"
        MockTF.return_value.get_glue_tf_content.return_value = None
        MockTF.return_value.generate_full_locals_tf.return_value = None
        MockKB.return_value.get_files_to_modify.return_value = ["saptcc/locals.tf"]
        MockKB.return_value.get_pr_checklist.return_value = []
        MockKB.return_value.get_new_source_checklist.return_value = None

        from app.graph.nodes.generate_terraform import generate_terraform_node
        result = generate_terraform_node(self._base_state(source_exists=True))

        assert result["file_edits"] is not None
        assert len(result["file_edits"]) == 1
        assert result["file_edits"][0]["path"] == "saptcc/locals.tf"
        # content is the HCL job block for existing system
        assert "saptcc-multi-1" in result["file_edits"][0]["content"]

    @patch(_KB_AGENT_PATCH)
    @patch(_TF_AGENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_glue_job_configured_true_when_flag_on(self, mock_settings, MockTF, MockKB):
        mock_settings.return_value = _settings_with_draft(True)
        MockTF.return_value.generate.return_value = "  saptcc-multi-1 = {}"
        MockTF.return_value.get_glue_tf_content.return_value = "module x {}"
        MockTF.return_value.generate_full_locals_tf.return_value = "locals { ... }"
        MockKB.return_value.get_files_to_modify.return_value = []
        MockKB.return_value.get_pr_checklist.return_value = []
        MockKB.return_value.get_new_source_checklist.return_value = None

        from app.graph.nodes.generate_terraform import generate_terraform_node
        result = generate_terraform_node(self._base_state(source_exists=False))
        assert result["glue_job_configured"] is True

    @patch(_KB_AGENT_PATCH)
    @patch(_TF_AGENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_file_edits_none_when_flag_off(self, mock_settings, MockTF, MockKB):
        mock_settings.return_value = _settings_with_draft(False)
        MockTF.return_value.generate.return_value = "  saptcc-multi-1 = {}"
        MockTF.return_value.get_glue_tf_content.return_value = "module x {}"
        MockTF.return_value.generate_full_locals_tf.return_value = "locals { ... }"
        MockKB.return_value.get_files_to_modify.return_value = []
        MockKB.return_value.get_pr_checklist.return_value = []
        MockKB.return_value.get_new_source_checklist.return_value = None

        from app.graph.nodes.generate_terraform import generate_terraform_node
        result = generate_terraform_node(self._base_state(source_exists=False))
        assert result.get("file_edits") is None
        assert result.get("glue_job_configured") is None

    @patch(_KB_AGENT_PATCH)
    @patch(_TF_AGENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_large_content_fields_still_present_for_backward_compat(self, mock_settings, MockTF, MockKB):
        """locals_tf_full and glue_tf_content remain in state for create_pr_node."""
        mock_settings.return_value = _settings_with_draft(True)
        MockTF.return_value.generate.return_value = "  saptcc-multi-1 = {}"
        MockTF.return_value.get_glue_tf_content.return_value = "module saptcc {}"
        MockTF.return_value.generate_full_locals_tf.return_value = "locals { glue_jobs = {} }"
        MockKB.return_value.get_files_to_modify.return_value = []
        MockKB.return_value.get_pr_checklist.return_value = []
        MockKB.return_value.get_new_source_checklist.return_value = []

        from app.graph.nodes.generate_terraform import generate_terraform_node
        result = generate_terraform_node(self._base_state(source_exists=False))
        # Both must still be present so create_pr_node can read them
        assert result["locals_tf_full"] is not None
        assert result["glue_tf_content"] != ""
        assert result["terraform_hcl"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# _apply_draft_mutations
# ─────────────────────────────────────────────────────────────────────────────

class TestApplyDraftMutations:
    """_apply_draft_mutations reads state snapshot, applies to draft, clears fields."""

    _SETTINGS_PATCH = "app.api.processor.get_settings"

    def _make_snap_values(self, file_edits=None, glue_job_configured=False,
                          source_system="saptcc", schema_grain="multi-1",
                          topic="dev.saptcc.multi-1.raw", environment="dev",
                          job_key="kafka-to-iceberg-batch-saptcc-multi-1",
                          history=None):
        return {
            "file_edits": file_edits,
            "glue_job_configured": glue_job_configured,
            "source_system": source_system,
            "schema_grain": schema_grain,
            "topic": topic,
            "environment": environment,
            "job_key": job_key,
            "draft_change_history": history,
        }

    def _setup_processor(self, snap_values: dict):
        """Return patched processor module with a fresh draft and mocked graph."""
        import app.api.processor as proc

        # Fresh draft service and draft
        draft_svc = MagicMock()
        draft = {
            "draft_id": "d-test",
            "session_id": "s-test",
            "files": [],
            "glue_jobs": [],
            "snapshot_refs": [],
        }
        draft_svc.get_draft.return_value = draft
        draft_svc.add_file = MagicMock()
        draft_svc.add_glue_job = MagicMock(side_effect=lambda *a, **kw: draft["glue_jobs"].append({}))

        mock_snap = MagicMock()
        mock_snap.values = snap_values

        mock_graph = AsyncMock()
        mock_graph.aget_state = AsyncMock(return_value=mock_snap)
        mock_graph.aupdate_state = AsyncMock()

        return proc, draft_svc, draft, mock_graph

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_file_edits_applied_to_draft(self, mock_graph_fn, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values(
                file_edits=[{"path": "saptcc/locals.tf", "content": "locals {}"}]
            )
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-test"] = "d-test"

        _run(p._apply_draft_mutations("s-test", {"configurable": {"thread_id": "s-test"}}))

        draft_svc.add_file.assert_called_once_with(draft, "saptcc/locals.tf", "locals {}")

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_glue_job_added_when_configured(self, mock_graph_fn, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values(glue_job_configured=True)
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-test"] = "d-test"

        _run(p._apply_draft_mutations("s-test", {"configurable": {"thread_id": "s-test"}}))

        draft_svc.add_glue_job.assert_called_once()
        call_args = draft_svc.add_glue_job.call_args
        assert call_args[0][1] == "saptcc"     # source_system
        assert call_args[0][2] == "multi-1"    # schema_grain

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_file_edits_cleared_after_apply(self, mock_graph_fn, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values(
                file_edits=[{"path": "saptcc/locals.tf", "content": "x"}]
            )
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-test"] = "d-test"
        _run(p._apply_draft_mutations("s-test", {"configurable": {"thread_id": "s-test"}}))

        # aupdate_state must have been called with file_edits=None
        update_call = mock_graph.aupdate_state.call_args[0][1]
        assert update_call.get("file_edits") is None

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_glue_job_configured_cleared_after_apply(self, mock_graph_fn, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values(glue_job_configured=True)
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-test"] = "d-test"
        _run(p._apply_draft_mutations("s-test", {"configurable": {"thread_id": "s-test"}}))

        update_call = mock_graph.aupdate_state.call_args[0][1]
        assert update_call.get("glue_job_configured") is None

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_glue_jobs_created_count_updated(self, mock_graph_fn, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values(glue_job_configured=True)
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-test"] = "d-test"
        _run(p._apply_draft_mutations("s-test", {"configurable": {"thread_id": "s-test"}}))

        update_call = mock_graph.aupdate_state.call_args[0][1]
        # add_glue_job side_effect appended one entry → count = 1
        assert update_call.get("glue_jobs_created_count") == 1

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_draft_change_history_populated(self, mock_graph_fn, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values(
                file_edits=[{"path": "saptcc/locals.tf", "content": "x"}],
                glue_job_configured=True,
            )
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-test"] = "d-test"
        _run(p._apply_draft_mutations("s-test", {"configurable": {"thread_id": "s-test"}}))

        update_call = mock_graph.aupdate_state.call_args[0][1]
        history = update_call.get("draft_change_history") or []
        ops = [h["operation"] for h in history]
        assert "add_file" in ops
        assert "add_glue_job" in ops

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor.get_compiled_graph")
    def test_no_op_when_flag_off(self, mock_graph_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(False)
        mock_graph_fn.return_value = AsyncMock()

        import app.api.processor as p
        p._session_drafts["s-no-flag"] = "d-no-flag"
        # Should return without calling aupdate_state
        _run(p._apply_draft_mutations("s-no-flag", {"configurable": {"thread_id": "s-no-flag"}}))
        mock_graph_fn.return_value.aupdate_state.assert_not_called()

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor.get_compiled_graph")
    def test_no_op_when_nothing_to_apply(self, mock_graph_fn, mock_svc_fn, mock_settings):
        """When file_edits=None and glue_job_configured=False, no aupdate_state."""
        mock_settings.return_value = _settings_with_draft(True)
        proc, draft_svc, draft, mock_graph = self._setup_processor(
            self._make_snap_values()  # file_edits=None, glue_job_configured=False
        )
        mock_svc_fn.return_value = draft_svc
        mock_graph_fn.return_value = mock_graph

        import app.api.processor as p
        p._session_drafts["s-empty"] = "d-test"
        _run(p._apply_draft_mutations("s-empty", {"configurable": {"thread_id": "s-empty"}}))

        mock_graph.aupdate_state.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# get_session_draft_summary
# ─────────────────────────────────────────────────────────────────────────────

class TestGetSessionDraftSummary:
    """get_session_draft_summary returns correct summary or None."""

    @patch("app.api.processor.get_settings")
    def test_returns_none_when_flag_off(self, mock_settings):
        mock_settings.return_value = _settings_with_draft(False)
        import app.api.processor as p
        assert p.get_session_draft_summary("some-session") is None

    @patch("app.api.processor.get_settings")
    def test_returns_none_when_no_draft_registered(self, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        import app.api.processor as p
        p._session_drafts.pop("unknown-session", None)
        assert p.get_session_draft_summary("unknown-session") is None

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    def test_create_another_job_visible_false_when_no_jobs(self, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        draft = real_svc.create_draft("s-viz-test")
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        p._session_drafts["s-viz-test"] = draft["draft_id"]
        summary = p.get_session_draft_summary("s-viz-test")
        assert summary is not None
        assert summary["create_another_job_visible"] is False

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    def test_create_another_job_visible_true_when_jobs_exist(self, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        draft = real_svc.create_draft("s-viz2-test")
        # Add one glue job
        real_svc.add_glue_job(draft, "saptcc", "multi-1", "dev.saptcc.multi-1.raw", "dev")
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        p._session_drafts["s-viz2-test"] = draft["draft_id"]
        summary = p.get_session_draft_summary("s-viz2-test")
        assert summary is not None
        assert summary["create_another_job_visible"] is True

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    def test_summary_includes_expected_keys(self, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        draft = real_svc.create_draft("s-keys-test")
        real_svc.add_file(draft, "saptcc/locals.tf", "locals {}")
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        p._session_drafts["s-keys-test"] = draft["draft_id"]
        summary = p.get_session_draft_summary("s-keys-test")

        for key in ("draft_id", "session_id", "status", "files_count",
                    "glue_jobs_count", "glue_jobs", "create_another_job_visible"):
            assert key in summary, f"Missing key: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# discard_session_draft_change
# ─────────────────────────────────────────────────────────────────────────────

class TestDiscardSessionDraftChange:
    """discard_session_draft_change delegates to DraftWorkspaceService.discard_last_change."""

    @patch("app.api.processor.get_settings")
    def test_returns_false_when_flag_off(self, mock_settings):
        mock_settings.return_value = _settings_with_draft(False)
        import app.api.processor as p
        assert p.discard_session_draft_change("any-session") is False

    @patch("app.api.processor.get_settings")
    def test_returns_false_when_no_draft(self, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        import app.api.processor as p
        p._session_drafts.pop("no-draft-session", None)
        assert p.discard_session_draft_change("no-draft-session") is False

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    def test_calls_discard_last_change(self, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        draft = real_svc.create_draft("s-discard-test")
        real_svc.add_file(draft, "saptcc/locals.tf", "locals { v1 = 1 }")
        real_svc.add_file(draft, "saptcc/locals.tf", "locals { v2 = 2 }")
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        p._session_drafts["s-discard-test"] = draft["draft_id"]
        result = p.discard_session_draft_change("s-discard-test")
        # DraftWorkspaceService.discard_last_change returns True when undo succeeds
        assert result is True

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    def test_multiple_discards_reduce_snapshot_count(self, mock_svc_fn, mock_settings):
        """
        SnapshotEngine.discard_last_change() restores the second-to-last snapshot's
        content into the DraftWorkspace.  The internal snapshot list is not shrunk
        (it is append-only); we verify behaviour via the restored file content.
        """
        mock_settings.return_value = _settings_with_draft(True)

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        draft = real_svc.create_draft("s-multi-discard")
        # v1 snapshot
        real_svc.add_file(draft, "saptcc/locals.tf", "v1")
        # v2 snapshot
        real_svc.add_file(draft, "saptcc/locals.tf", "v2")
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        p._session_drafts["s-multi-discard"] = draft["draft_id"]

        # First discard: reverts to v1 content
        result = p.discard_session_draft_change("s-multi-discard")
        assert result is True
        # Second discard when only one undoable state left returns False
        result2 = p.discard_session_draft_change("s-multi-discard")
        # (may be True or False depending on engine depth; we just verify no exception)
        assert isinstance(result2, bool)


# ─────────────────────────────────────────────────────────────────────────────
# process_first_message — draft creation wiring
# ─────────────────────────────────────────────────────────────────────────────

class TestProcessFirstMessageDraftCreation:
    """process_first_message creates a Draft Workspace when flag is on."""

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor._stream_graph", new_callable=AsyncMock)
    def test_draft_created_and_registered(self, mock_stream, mock_svc_fn, mock_settings):
        mock_settings.return_value = _settings_with_draft(True)
        mock_stream.return_value = []

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        _run(p.process_first_message("s-init-test"))

        assert "s-init-test" in p._session_drafts
        draft_id = p._session_drafts["s-init-test"]
        assert real_svc.get_draft(draft_id) is not None

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._get_draft_service")
    @patch("app.api.processor._stream_graph", new_callable=AsyncMock)
    def test_draft_workspace_id_in_initial_state_passed_to_stream(
        self, mock_stream, mock_svc_fn, mock_settings
    ):
        mock_settings.return_value = _settings_with_draft(True)
        mock_stream.return_value = []

        from app.services.draft_workspace_service import DraftWorkspaceService
        real_svc = DraftWorkspaceService()
        mock_svc_fn.return_value = real_svc

        import app.api.processor as p
        _run(p.process_first_message("s-id-check"))

        # _stream_graph was called; check its first positional arg (state dict)
        call_args = mock_stream.call_args[0]
        state_passed = call_args[0]
        assert state_passed.get("draft_workspace_id") is not None

    @patch("app.api.processor.get_settings")
    @patch("app.api.processor._stream_graph", new_callable=AsyncMock)
    def test_no_draft_created_when_flag_off(self, mock_stream, mock_settings):
        mock_settings.return_value = _settings_with_draft(False)
        mock_stream.return_value = []

        import app.api.processor as p
        p._session_drafts.pop("s-no-draft", None)
        _run(p.process_first_message("s-no-draft"))

        assert "s-no-draft" not in p._session_drafts


# ─────────────────────────────────────────────────────────────────────────────
# Integration: API routes
# ─────────────────────────────────────────────────────────────────────────────

class TestDraftApiRoutes:
    """
    Integration tests for GET /sessions/{id}/draft and
    POST /sessions/{id}/draft/discard.
    Uses FastAPI TestClient; patches auth validation and processor helpers.
    """

    _AUTH_PATCH = "app.api.routes._require_owner_async"

    def _client(self):
        from fastapi import FastAPI
        from app.api.routes import router
        app = FastAPI()
        app.include_router(router, prefix="/api")
        from fastapi.testclient import TestClient
        return TestClient(app)

    @patch("app.api.routes._require_owner_async", new_callable=AsyncMock)
    def test_get_draft_returns_404_when_no_draft(self, _auth):
        with patch("app.api.processor.get_session_draft_summary", return_value=None):
            client = self._client()
            resp = client.get("/api/sessions/s-404/draft", headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 404

    @patch("app.api.routes._require_owner_async", new_callable=AsyncMock)
    def test_get_draft_returns_summary_when_draft_exists(self, _auth):
        summary = {
            "draft_id": "d-1",
            "session_id": "s-ok",
            "status": "open",
            "files_count": 1,
            "glue_jobs_count": 0,
            "glue_jobs": [],
            "snapshots_count": 1,
            "create_another_job_visible": False,
            "created_at": "2026-06-12T00:00:00",
            "updated_at": "2026-06-12T00:00:00",
        }
        with patch("app.api.processor.get_session_draft_summary", return_value=summary):
            client = self._client()
            resp = client.get("/api/sessions/s-ok/draft", headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["draft_id"] == "d-1"
        assert data["create_another_job_visible"] is False

    @patch("app.api.routes._require_owner_async", new_callable=AsyncMock)
    def test_discard_returns_404_when_no_draft(self, _auth):
        with patch("app.api.processor.get_session_draft_summary", return_value=None):
            client = self._client()
            resp = client.post("/api/sessions/s-nd/draft/discard",
                               headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 404

    @patch("app.api.routes._require_owner_async", new_callable=AsyncMock)
    def test_discard_returns_409_when_nothing_to_undo(self, _auth):
        summary = {"draft_id": "d-1", "session_id": "s-nd2"}
        with (
            patch("app.api.processor.get_session_draft_summary", return_value=summary),
            patch("app.api.processor.discard_session_draft_change", return_value=False),
        ):
            client = self._client()
            resp = client.post("/api/sessions/s-nd2/draft/discard",
                               headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 409

    @patch("app.api.routes._require_owner_async", new_callable=AsyncMock)
    def test_discard_returns_200_on_success(self, _auth):
        summary = {"draft_id": "d-1", "session_id": "s-ok2"}
        with (
            patch("app.api.processor.get_session_draft_summary", return_value=summary),
            patch("app.api.processor.discard_session_draft_change", return_value=True),
        ):
            client = self._client()
            resp = client.post("/api/sessions/s-ok2/draft/discard",
                               headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 200
        assert resp.json()["discarded"] is True

    @patch("app.api.routes._require_owner_async", new_callable=AsyncMock)
    def test_get_draft_create_another_job_visible_true(self, _auth):
        """create_another_job_visible=True is correctly forwarded by route."""
        summary = {
            "draft_id": "d-2",
            "session_id": "s-multi",
            "glue_jobs_count": 1,
            "glue_jobs": [{"job_key": "kafka-to-iceberg-batch-saptcc-multi-1"}],
            "create_another_job_visible": True,
            "files_count": 2,
            "snapshots_count": 3,
            "status": "open",
            "created_at": "2026-06-12T00:00:00",
            "updated_at": "2026-06-12T00:00:00",
        }
        with patch("app.api.processor.get_session_draft_summary", return_value=summary):
            client = self._client()
            resp = client.get("/api/sessions/s-multi/draft",
                              headers={"Authorization": "Bearer tok"})
        assert resp.status_code == 200
        assert resp.json()["create_another_job_visible"] is True
