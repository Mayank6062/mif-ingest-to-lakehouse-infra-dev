"""
Tests for the audit logging service (app/services/audit_log.py).

Covers:
  - Schema validation (all required fields, correct types, event_version == 1)
  - Timestamp format (UTC ISO-8601 with milliseconds: YYYY-MM-DDTHH:MM:SS.mmmZ)
  - All 6 event types: session_created, approval_received, approval_rejected,
    pr_creation_started, pr_creation_succeeded, pr_creation_failed
  - log_event() never raises under any failure condition
  - Forbidden field NAMES never appear in any emitted record
  - Forbidden field VALUES never appear in any emitted record
  - Audit logging failure does not block PR creation (success + failure paths)
"""

import json
import re

import pytest
from unittest.mock import patch

from app.services.audit_log import log_event, _now_iso


# ── Shared test helpers ────────────────────────────────────────────────────────

def _emit(event: str, actor: str, state: dict, **kwargs) -> dict:
    """Call log_event, capture the raw emitted JSON string, return parsed record."""
    captured: list[str] = []
    with patch("app.services.audit_log._audit_logger") as mock_logger:
        mock_logger.info.side_effect = captured.append
        log_event(event, actor, state, **kwargs)
    assert captured, f"No audit record was emitted for event '{event}'"
    return json.loads(captured[0])


_FULL_STATE: dict = {
    "session_id":    "test-session-uuid-1234",
    "topic":         "mif.saptcc.cdhdr.v1",
    "source_system": "saptcc",
    "schema_grain":  "cdhdr",
    "job_key":       "kafka-to-iceberg-batch-saptcc-cdhdr",
    "environment":   "dev",
    "branch_name":   "feature/glue-job-saptcc-cdhdr-20260606142301",
    "user_approved": True,
}

_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

_REQUIRED_FIELDS = [
    "event_version", "event", "actor", "correlation_id", "ts",
    "session_id", "topic", "source_system", "schema_grain", "job_key",
    "environment", "branch_name", "approved", "pr_number", "pr_url", "error",
]

_FORBIDDEN_FIELD_NAMES = [
    "terraform_hcl",
    "locals_tf_full",
    "glue_tf_content",
    "github_token",
    "azure_openai_api_key",
    "session_token",
    "Authorization",
    "authorization",
]


# ── Timestamp ──────────────────────────────────────────────────────────────────

class TestTimestamp:
    def test_format_matches_utc_iso8601_with_millis(self):
        ts = _now_iso()
        assert _TIMESTAMP_RE.match(ts), (
            f"Timestamp {ts!r} does not match expected format YYYY-MM-DDTHH:MM:SS.mmmZ"
        )

    def test_ends_with_z_utc_designator(self):
        assert _now_iso().endswith("Z"), "Timestamp must end with Z (UTC)"

    def test_millisecond_component_is_three_digits(self):
        ts = _now_iso()
        # Format: 2026-06-06T14:23:01.456Z — milliseconds at index 20:23
        millis_part = ts[20:23]
        assert millis_part.isdigit() and len(millis_part) == 3, (
            f"Expected 3-digit milliseconds, got {millis_part!r} in {ts!r}"
        )

    def test_emitted_record_ts_matches_format(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert _TIMESTAMP_RE.match(record["ts"]), (
            f"Emitted ts {record['ts']!r} does not match expected format"
        )


# ── Schema validation ──────────────────────────────────────────────────────────

class TestSchema:
    def test_all_required_fields_present(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        for field in _REQUIRED_FIELDS:
            assert field in record, f"Required field '{field}' missing from audit record"

    def test_event_version_is_integer_1(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert record["event_version"] == 1
        assert isinstance(record["event_version"], int)

    def test_correlation_id_equals_session_id(self):
        state = {**_FULL_STATE, "session_id": "corr-test-session-abc"}
        record = _emit("approval_received", "user", state)
        assert record["correlation_id"] == "corr-test-session-abc"
        assert record["session_id"]     == "corr-test-session-abc"
        assert record["correlation_id"] == record["session_id"]

    def test_actor_user_for_approval(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert record["actor"] == "user"

    def test_actor_system_for_pr_events(self):
        record = _emit("pr_creation_started", "system", _FULL_STATE)
        assert record["actor"] == "system"

    def test_record_is_valid_json(self):
        captured: list[str] = []
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = captured.append
            log_event("approval_received", "user", _FULL_STATE)
        assert captured
        parsed = json.loads(captured[0])
        assert isinstance(parsed, dict)

    def test_pr_fields_null_before_pr_exists(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert record["pr_number"] is None
        assert record["pr_url"]    is None
        assert record["error"]     is None

    def test_branch_name_null_when_absent_from_state(self):
        state = {k: v for k, v in _FULL_STATE.items() if k != "branch_name"}
        record = _emit("approval_received", "user", state)
        assert record["branch_name"] is None

    def test_all_business_fields_populated(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert record["topic"]         == "mif.saptcc.cdhdr.v1"
        assert record["source_system"] == "saptcc"
        assert record["schema_grain"]  == "cdhdr"
        assert record["job_key"]       == "kafka-to-iceberg-batch-saptcc-cdhdr"
        assert record["environment"]   == "dev"
        assert record["session_id"]    == "test-session-uuid-1234"


# ── Per-event tests ────────────────────────────────────────────────────────────

class TestSessionCreated:
    def test_event_name(self):
        assert _emit("session_created", "system", {"session_id": "sid-new"})["event"] == "session_created"

    def test_actor_is_system(self):
        assert _emit("session_created", "system", {"session_id": "sid-new"})["actor"] == "system"

    def test_session_id_and_correlation_id_populated(self):
        record = _emit("session_created", "system", {"session_id": "sid-created"})
        assert record["session_id"]     == "sid-created"
        assert record["correlation_id"] == "sid-created"

    def test_business_fields_null_at_session_creation(self):
        record = _emit("session_created", "system", {"session_id": "sid-new"})
        assert record["topic"]         is None
        assert record["source_system"] is None
        assert record["job_key"]       is None
        assert record["pr_number"]     is None


class TestApprovalReceived:
    def test_event_name(self):
        assert _emit("approval_received", "user", _FULL_STATE)["event"] == "approval_received"

    def test_actor_is_user(self):
        assert _emit("approval_received", "user", _FULL_STATE)["actor"] == "user"

    def test_approved_is_true(self):
        assert _emit("approval_received", "user", _FULL_STATE)["approved"] is True

    def test_branch_name_populated(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert record["branch_name"] == "feature/glue-job-saptcc-cdhdr-20260606142301"

    def test_pr_fields_null(self):
        record = _emit("approval_received", "user", _FULL_STATE)
        assert record["pr_number"] is None
        assert record["pr_url"]    is None
        assert record["error"]     is None


class TestApprovalRejected:
    _REJECTED = {**_FULL_STATE, "user_approved": False}

    def test_event_name(self):
        assert _emit("approval_rejected", "user", self._REJECTED)["event"] == "approval_rejected"

    def test_actor_is_user(self):
        assert _emit("approval_rejected", "user", self._REJECTED)["actor"] == "user"

    def test_approved_is_false(self):
        assert _emit("approval_rejected", "user", self._REJECTED)["approved"] is False

    def test_no_pr_fields_set(self):
        record = _emit("approval_rejected", "user", self._REJECTED)
        assert record["pr_number"] is None
        assert record["pr_url"]    is None
        assert record["error"]     is None


class TestPRCreationStarted:
    def test_event_name(self):
        assert _emit("pr_creation_started", "system", _FULL_STATE)["event"] == "pr_creation_started"

    def test_actor_is_system(self):
        assert _emit("pr_creation_started", "system", _FULL_STATE)["actor"] == "system"

    def test_pr_fields_null(self):
        record = _emit("pr_creation_started", "system", _FULL_STATE)
        assert record["pr_number"] is None
        assert record["pr_url"]    is None
        assert record["error"]     is None


class TestPRCreationSucceeded:
    _KWARGS = {"pr_number": 42, "pr_url": "https://github.com/org/repo/pull/42"}

    def test_event_name(self):
        assert _emit("pr_creation_succeeded", "system", _FULL_STATE, **self._KWARGS)["event"] == "pr_creation_succeeded"

    def test_actor_is_system(self):
        assert _emit("pr_creation_succeeded", "system", _FULL_STATE, **self._KWARGS)["actor"] == "system"

    def test_pr_number_populated(self):
        record = _emit("pr_creation_succeeded", "system", _FULL_STATE, **self._KWARGS)
        assert record["pr_number"] == 42

    def test_pr_url_populated(self):
        record = _emit("pr_creation_succeeded", "system", _FULL_STATE, **self._KWARGS)
        assert record["pr_url"] == "https://github.com/org/repo/pull/42"

    def test_error_null_on_success(self):
        record = _emit("pr_creation_succeeded", "system", _FULL_STATE, **self._KWARGS)
        assert record["error"] is None


class TestPRCreationFailed:
    _ERROR = "GitHub API 422: Unprocessable Entity — branch already exists"

    def test_event_name(self):
        assert _emit("pr_creation_failed", "system", _FULL_STATE, error=self._ERROR)["event"] == "pr_creation_failed"

    def test_actor_is_system(self):
        assert _emit("pr_creation_failed", "system", _FULL_STATE, error=self._ERROR)["actor"] == "system"

    def test_error_populated(self):
        record = _emit("pr_creation_failed", "system", _FULL_STATE, error=self._ERROR)
        assert record["error"] == self._ERROR

    def test_pr_number_and_url_null_on_failure(self):
        record = _emit("pr_creation_failed", "system", _FULL_STATE, error=self._ERROR)
        assert record["pr_number"] is None
        assert record["pr_url"]    is None


# ── log_event() never raises ───────────────────────────────────────────────────

class TestLogEventNeverRaises:
    def test_empty_state_does_not_raise(self):
        log_event("approval_received", "user", {})

    def test_none_values_in_state_do_not_raise(self):
        log_event("pr_creation_failed", "system", {
            "session_id": None, "topic": None, "source_system": None,
            "schema_grain": None, "job_key": None, "environment": None,
        }, error=None)

    def test_audit_logger_oserror_does_not_propagate(self):
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = OSError("disk full — no space left on device")
            log_event("approval_received", "user", _FULL_STATE)

    def test_audit_logger_runtime_error_does_not_propagate(self):
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = RuntimeError("handler misconfigured")
            log_event("pr_creation_started", "system", _FULL_STATE)

    def test_json_dumps_error_does_not_propagate(self):
        with patch("app.services.audit_log.json") as mock_json:
            mock_json.dumps.side_effect = TypeError("object is not JSON serializable")
            log_event("approval_received", "user", _FULL_STATE)

    def test_log_event_always_returns_none(self):
        assert log_event("approval_received", "user", _FULL_STATE) is None

    def test_log_event_returns_none_on_logger_failure(self):
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = RuntimeError("handler crashed")
            result = log_event("approval_received", "user", _FULL_STATE)
        assert result is None


# ── Forbidden fields — names and values must never appear in emitted records ───

class TestForbiddenFieldsNeverLogged:
    """
    Verify that forbidden field NAMES and their VALUES never appear in any
    emitted audit record, even when those keys are present in the state dict
    passed to log_event().  Secure by construction — log_event() extracts
    only explicitly named fields; it never spreads or serialises the state whole.
    """

    _FORBIDDEN_MARKERS = {
        "terraform_hcl":        "FORBIDDEN_TERRAFORM_HCL_PAYLOAD",
        "locals_tf_full":       "FORBIDDEN_LOCALS_TF_FULL_PAYLOAD",
        "glue_tf_content":      "FORBIDDEN_GLUE_TF_CONTENT_PAYLOAD",
        "github_token":         "FORBIDDEN_GITHUB_TOKEN_PAYLOAD",
        "azure_openai_api_key": "FORBIDDEN_AZURE_OPENAI_KEY_PAYLOAD",
        "session_token":        "FORBIDDEN_SESSION_TOKEN_PAYLOAD",
        "Authorization":        "FORBIDDEN_AUTH_HEADER_PAYLOAD",
        "authorization":        "FORBIDDEN_AUTH_LOWER_PAYLOAD",
    }

    def _state_with_forbidden_fields(self) -> dict:
        """State that contains ALL forbidden keys with unique recognisable marker values."""
        state = dict(_FULL_STATE)
        state.update(self._FORBIDDEN_MARKERS)
        return state

    def _capture_raw(self, event: str, actor: str, state: dict, **kwargs) -> str:
        """Call log_event and return the raw emitted JSON string."""
        captured: list[str] = []
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = captured.append
            log_event(event, actor, state, **kwargs)
        return captured[0] if captured else ""

    @pytest.mark.parametrize("event,actor,extra_kwargs", [
        ("session_created",       "system", {}),
        ("approval_received",     "user",   {}),
        ("approval_rejected",     "user",   {}),
        ("pr_creation_started",   "system", {}),
        ("pr_creation_succeeded", "system", {"pr_number": 1, "pr_url": "https://github.com/test/pr/1"}),
        ("pr_creation_failed",    "system", {"error": "test error"}),
    ])
    def test_forbidden_field_names_absent_from_all_events(self, event, actor, extra_kwargs):
        """No forbidden field NAME must appear as a JSON key in any emitted record."""
        state = self._state_with_forbidden_fields()
        emitted = self._capture_raw(event, actor, state, **extra_kwargs)
        for field_name in _FORBIDDEN_FIELD_NAMES:
            assert field_name not in emitted, (
                f"Forbidden field name '{field_name}' leaked into '{event}' audit record:\n{emitted}"
            )

    @pytest.mark.parametrize("event,actor,extra_kwargs", [
        ("session_created",       "system", {}),
        ("approval_received",     "user",   {}),
        ("approval_rejected",     "user",   {}),
        ("pr_creation_started",   "system", {}),
        ("pr_creation_succeeded", "system", {"pr_number": 1, "pr_url": "https://github.com/test/pr/1"}),
        ("pr_creation_failed",    "system", {"error": "test error"}),
    ])
    def test_forbidden_field_values_absent_from_all_events(self, event, actor, extra_kwargs):
        """No forbidden field VALUE (marker sentinel) must appear in any emitted record."""
        state = self._state_with_forbidden_fields()
        emitted = self._capture_raw(event, actor, state, **extra_kwargs)
        for field_name, marker_value in self._FORBIDDEN_MARKERS.items():
            assert marker_value not in emitted, (
                f"Forbidden value for '{field_name}' ('{marker_value}') leaked into "
                f"'{event}' audit record:\n{emitted}"
            )


# ── Audit logging failure must never block PR creation ────────────────────────

class TestAuditDoesNotBlockPRCreation:
    """
    Verify that any audit logging failure (OSError, RuntimeError, etc.) is
    fully absorbed by log_event() and does not prevent create_pr_node from
    returning a result — on both the success path and the failure path.
    """

    def _make_pr_state(self) -> dict:
        return {
            "session_id":    "sid-block-test-001",
            "user_approved": True,
            "source_system": "saptcc",
            "schema_grain":  "cdhdr",
            "topic":         "mif.saptcc.cdhdr.v1",
            "job_key":       "kafka-to-iceberg-batch-saptcc-cdhdr",
            "environment":   "dev",
            "branch_name":   None,
            "messages":      [],
        }

    def test_pr_created_successfully_when_audit_logger_raises(self):
        """PR creation must succeed even when every log_event call fails internally."""
        from app.graph.nodes.create_pr import create_pr_node
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = OSError("disk full")
            with patch("app.graph.nodes.create_pr.GitHubService") as MockSvc:
                svc = MockSvc.return_value
                svc.make_branch_name.return_value = "feature/glue-job-saptcc-cdhdr-20260606"
                svc.create_pr.return_value = {
                    "pr_url":         "https://github.com/org/repo/pull/42",
                    "branch_name":    "feature/glue-job-saptcc-cdhdr-20260606",
                    "pr_number":      42,
                    "files_modified": ["saptcc/locals.tf"],
                }
                result = create_pr_node(self._make_pr_state())
        assert result.get("current_step") == "pr_success"
        assert result.get("pr_number")    == 42
        assert result.get("pr_url")       == "https://github.com/org/repo/pull/42"

    def test_pr_failure_state_returned_when_audit_logger_raises(self):
        """PR failure handling must complete even when all audit log calls fail."""
        from app.graph.nodes.create_pr import create_pr_node
        with patch("app.services.audit_log._audit_logger") as mock_logger:
            mock_logger.info.side_effect = OSError("disk full")
            with patch("app.graph.nodes.create_pr.GitHubService") as MockSvc:
                svc = MockSvc.return_value
                svc.make_branch_name.return_value = "feature/glue-job-saptcc-cdhdr-20260606"
                svc.create_pr.side_effect = RuntimeError("GitHub rate limit exceeded")
                result = create_pr_node(self._make_pr_state())
        assert result.get("current_step") == "create_pr"
        assert "rate limit" in result.get("error_message", "")
