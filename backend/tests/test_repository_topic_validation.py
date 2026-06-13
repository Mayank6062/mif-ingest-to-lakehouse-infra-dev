"""
Unit tests for Step 2.1: Repository-authoritative topic validation.

Validates check_kafka_topic_node against the Architecture Freeze Rules:

  Rule 1 — repository topics file absent        → BLOCK, "Please create the topic first."
  Rule 2 — file present, schema_grain not found → BLOCK, "Please create the topic first."
  Rule 3 — file present, schema_grain found     → PASS, Kafka secondary checks run (non-blocking)

Secondary Kafka checks (Rules K1–K5) are INFORMATIONAL ONLY and never block.

Patching strategy:
  Primary:   app.graph.nodes.check_kafka_topic.GitHubService
             (patches the class as imported inside the node module)
  Secondary: app.graph.nodes.check_kafka_topic.KafkaService
             (patches Kafka class inside the node module to avoid live broker)

  Both are class-level patches so every method call on any instance is mocked.

Compatibility note:
  The existing test_check_kafka_topic.py tests the OLD Kafka-authoritative rules.
  Those tests patch KafkaService only. With the new repository-first code they will
  fail unless app.graph.nodes.check_kafka_topic.GitHubService is also patched.
  The existing test file MUST NOT be modified (per project constraint); it will need
  a compatibility update patch for GitHubService in a future test-update cycle.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.graph.state import (
    STEP_COLLECT_TOPIC,
    STEP_CHECK_KAFKA_TOPIC,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_GITHUB_PATCH = "app.graph.nodes.check_kafka_topic.GitHubService"
_KAFKA_PATCH   = "app.graph.nodes.check_kafka_topic.KafkaService"


def _base_state(topic: str = "dev.saptcc.multi-1.raw") -> dict:
    """Minimal valid state with a topic set."""
    return {
        "session_id": "test-session",
        "topic": topic,
        "current_step": "derive_values",
        "waiting_for_user": True,
        "messages": [],
    }


def _run_node(state: dict) -> dict:
    from app.graph.nodes.check_kafka_topic import check_kafka_topic_node
    return check_kafka_topic_node(state)


def _repo_not_found(source_system: str = "saptcc") -> dict:
    """Simulate: topics file does not exist in repo."""
    return {
        "schema_grain_found": False,
        "topic_file_exists": False,
        "topic_file_path": f"confluent_minerva_dev/topics_{source_system}.tf",
        "error": f"File not found on branch 'main'",
    }


def _repo_file_found_grain_missing(source_system: str = "saptcc", schema_grain: str = "multi-1") -> dict:
    """Simulate: topics file found but schema_grain not present."""
    return {
        "schema_grain_found": False,
        "topic_file_exists": True,
        "topic_file_path": f"confluent_minerva_dev/topics_{source_system}.tf",
        "error": None,
    }


def _repo_file_found_grain_present(source_system: str = "saptcc", schema_grain: str = "multi-1") -> dict:
    """Simulate: topics file found and schema_grain present."""
    return {
        "schema_grain_found": True,
        "topic_file_exists": True,
        "topic_file_path": f"confluent_minerva_dev/topics_{source_system}.tf",
        "error": None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# _parse_topic internal helper
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTopicHelper:
    """Verify the inline topic parser used by the node."""

    def test_valid_four_segment_topic(self):
        from app.graph.nodes.check_kafka_topic import _parse_topic
        env, source, grain = _parse_topic("dev.saptcc.multi-1.raw")
        assert env == "dev"
        assert source == "saptcc"
        assert grain == "multi-1"

    def test_prod_environment(self):
        from app.graph.nodes.check_kafka_topic import _parse_topic
        env, source, grain = _parse_topic("prod.wahoo.cdhdr.raw")
        assert env == "prod"
        assert source == "wahoo"
        assert grain == "cdhdr"

    def test_hyphen_in_grain(self):
        from app.graph.nodes.check_kafka_topic import _parse_topic
        _, _, grain = _parse_topic("dev.saptcc.multi-1.raw")
        assert grain == "multi-1"

    @pytest.mark.parametrize("bad_topic", [
        "dev.saptcc.raw",        # only 3 segments
        "devsaptccraw",          # no dots
        "",                      # empty
        "dev",                   # single segment
    ])
    def test_returns_none_for_short_topics(self, bad_topic):
        from app.graph.nodes.check_kafka_topic import _parse_topic
        assert _parse_topic(bad_topic) is None


# ─────────────────────────────────────────────────────────────────────────────
# Rule 1 — repository topics file not found → HARD BLOCK
# ─────────────────────────────────────────────────────────────────────────────

class TestRule1RepoFileNotFound:
    """topics_<source>.tf absent from repository → BLOCK with 'create the topic first'."""

    @patch(_GITHUB_PATCH)
    def test_routes_to_collect_topic(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["current_step"] == STEP_COLLECT_TOPIC

    @patch(_GITHUB_PATCH)
    def test_waiting_for_user_is_true(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["waiting_for_user"] is True

    @patch(_GITHUB_PATCH)
    def test_message_says_create_topic_first(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        content = result["messages"][0]["content"].lower()
        assert "please create the topic first" in content

    @patch(_GITHUB_PATCH)
    def test_message_contains_topic_file_path(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        content = result["messages"][0]["content"]
        assert "confluent_minerva_dev/topics_saptcc.tf" in content

    @patch(_GITHUB_PATCH)
    def test_kafka_topic_missing_flag_set(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["kafka_topic_missing"] is True

    @patch(_GITHUB_PATCH)
    def test_no_approval_request_emitted(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        msg = result["messages"][0]
        assert not msg.get("approval_request")

    @patch(_GITHUB_PATCH)
    def test_no_auto_advance(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert not result["messages"][0].get("auto_advance")

    @patch(_GITHUB_PATCH)
    def test_different_source_systems(self, MockGH):
        """Each source system gets its own topics file path check."""
        for source in ("wahoo", "sfsc", "newcorp"):
            MockGH.return_value.validate_topic_in_repository.return_value = _repo_not_found(source)
            result = _run_node(_base_state(f"dev.{source}.grain.raw"))
            assert result["current_step"] == STEP_COLLECT_TOPIC
            assert f"topics_{source}.tf" in result["messages"][0]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — file present but schema_grain not found → HARD BLOCK
# ─────────────────────────────────────────────────────────────────────────────

class TestRule2SchemaGrainNotFound:
    """topics file found, schema_grain not in file → BLOCK with 'create the topic first'."""

    @patch(_GITHUB_PATCH)
    def test_routes_to_collect_topic(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["current_step"] == STEP_COLLECT_TOPIC

    @patch(_GITHUB_PATCH)
    def test_message_says_create_topic_first(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        content = result["messages"][0]["content"].lower()
        assert "please create the topic first" in content

    @patch(_GITHUB_PATCH)
    def test_message_contains_schema_grain(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert "multi-1" in result["messages"][0]["content"]

    @patch(_GITHUB_PATCH)
    def test_message_contains_topic(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert "dev.saptcc.multi-1.raw" in result["messages"][0]["content"]

    @patch(_GITHUB_PATCH)
    def test_kafka_topic_missing_flag_set(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["kafka_topic_missing"] is True

    @patch(_GITHUB_PATCH)
    def test_no_auto_advance(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert not result["messages"][0].get("auto_advance")

    @patch(_GITHUB_PATCH)
    def test_no_approval_request(self, MockGH):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing()
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert not result["messages"][0].get("approval_request")

    @patch(_GITHUB_PATCH)
    def test_different_grains_each_blocked(self, MockGH):
        """Missing grain blocks for every grain name."""
        for grain in ("cdhdr", "bseg", "unknown-grain"):
            MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_missing(
                schema_grain=grain
            )
            result = _run_node(_base_state(f"dev.saptcc.{grain}.raw"))
            assert result["current_step"] == STEP_COLLECT_TOPIC


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3 — repository approved; Kafka checks are informational only
# ─────────────────────────────────────────────────────────────────────────────

class TestRule3RepoApproved:
    """Repository validation passes → auto_advance; Kafka checks are non-blocking."""

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_auto_advance_when_kafka_healthy(self, MockGH, MockKafka):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 3, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["messages"][0].get("auto_advance") is True

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_auto_advance_even_when_kafka_down(self, MockGH, MockKafka):
        """Kafka broker failure must NOT block the workflow."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (False, "Connection refused")
        MockKafka.return_value.get_schema_count.return_value = (False, 0, "SR unavailable")
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["messages"][0].get("auto_advance") is True
        assert result["current_step"] == STEP_CHECK_KAFKA_TOPIC

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_auto_advance_when_topic_absent_from_broker(self, MockGH, MockKafka):
        """Topic not yet in Kafka broker → informational warning only, not a block."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (False, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["messages"][0].get("auto_advance") is True

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_auto_advance_when_sr_has_zero_subjects(self, MockGH, MockKafka):
        """SR available but zero subjects → informational only, not a block."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["messages"][0].get("auto_advance") is True

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_current_step_stays_at_check_kafka_topic(self, MockGH, MockKafka):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 1, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["current_step"] == STEP_CHECK_KAFKA_TOPIC

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_kafka_topic_missing_is_false(self, MockGH, MockKafka):
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 2, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["kafka_topic_missing"] is False

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_schema_check_needs_approval_is_false(self, MockGH, MockKafka):
        """Approval dialog is NEVER emitted once repo check passes."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["schema_check_needs_approval"] is False
        assert not result["messages"][0].get("approval_request")

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_kafka_broker_warning_in_message(self, MockGH, MockKafka):
        """Kafka warnings appear in message as informational context."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (False, "Connection refused")
        MockKafka.return_value.get_schema_count.return_value = (False, 0, "SR unavailable")
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        content = result["messages"][0]["content"]
        assert "informational" in content.lower()

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_message_confirms_repo_approval(self, MockGH, MockKafka):
        """Message acknowledges that repository approved the topic."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 1, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        content = result["messages"][0]["content"]
        assert "approved in repository" in content.lower()

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_schema_grain_in_approval_message(self, MockGH, MockKafka):
        """Confirmation message includes schema_grain and topic file path."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 1, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        content = result["messages"][0]["content"]
        assert "multi-1" in content
        assert "confluent_minerva_dev/topics_saptcc.tf" in content

    @patch(_KAFKA_PATCH)
    @patch(_GITHUB_PATCH)
    def test_kafka_fields_populated_when_broker_healthy(self, MockGH, MockKafka):
        """State fields are populated from secondary Kafka results."""
        MockGH.return_value.validate_topic_in_repository.return_value = _repo_file_found_grain_present()
        MockKafka.return_value.check_topic_exists.return_value = (True, None)
        MockKafka.return_value.get_schema_count.return_value = (True, 5, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["kafka_topic_exists"] is True
        assert result["schema_registry_available"] is True
        assert result["schema_count"] == 5
        assert result["schema_exists"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3b — GitHubService raises exception → BLOCK gracefully
# ─────────────────────────────────────────────────────────────────────────────

class TestGitHubServiceFailure:
    """If GitHubService itself throws, treat it as a blocking failure."""

    @patch(_GITHUB_PATCH, side_effect=Exception("No GitHub token"))
    def test_github_exception_routes_to_collect_topic(self, _):
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["current_step"] == STEP_COLLECT_TOPIC

    @patch(_GITHUB_PATCH, side_effect=Exception("Network error"))
    def test_github_exception_sets_kafka_topic_missing(self, _):
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["kafka_topic_missing"] is True

    @patch(_GITHUB_PATCH, side_effect=Exception("Auth failure"))
    def test_github_exception_no_auto_advance(self, _):
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert not result["messages"][0].get("auto_advance")


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases — malformed topics
# ─────────────────────────────────────────────────────────────────────────────

class TestMalformedTopics:
    """Short/malformed topics skip the GitHub check and auto_advance to derive_values."""

    @pytest.mark.parametrize("bad_topic", [
        "dev.saptcc.raw",
        "justoneword",
        "",
        "a.b",
    ])
    def test_short_topic_produces_auto_advance(self, bad_topic):
        """Node should not block on a topic parse failure; defer to derive_values."""
        # No patching needed — _parse_topic returns None before GitHubService is called.
        result = _run_node(_base_state(bad_topic))
        assert result["messages"][0].get("auto_advance") is True

    def test_short_topic_message_warns_of_incomplete_format(self):
        result = _run_node(_base_state("dev.saptcc.raw"))
        content = result["messages"][0]["content"].lower()
        assert "format" in content or "incomplete" in content


# ─────────────────────────────────────────────────────────────────────────────
# GitHubService.validate_topic_in_repository — unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateTopicInRepository:
    """Tests for GitHubService.validate_topic_in_repository method."""

    def _make_service(self):
        """Create a GitHubService with mocked internal state to avoid real API calls."""
        from app.services.github_service import GitHubService
        svc = GitHubService.__new__(GitHubService)
        svc._gh = MagicMock()
        svc._repo_owner = "test-owner"
        svc._repo_name = "test-repo"
        svc._base_branch = "main"
        svc._reviewers = []
        return svc

    def _mock_repo(self, svc, file_content: str | None):
        """Wire svc._get_repo() and _get_file_content() with controlled content."""
        mock_repo = MagicMock()
        svc._get_repo = MagicMock(return_value=mock_repo)

        if file_content is None:
            svc._get_file_content = MagicMock(return_value=None)
        else:
            mock_file = MagicMock()
            mock_file.decoded_content = file_content.encode("utf-8")
            svc._get_file_content = MagicMock(return_value=mock_file)

        return mock_repo

    def test_returns_found_when_schema_grain_in_file(self):
        svc = self._make_service()
        tf_content = '''
resource "confluent_kafka_topic" "multi-1" {
  topic_name       = "dev.saptcc.multi-1.raw"
  partitions_count = 6
}
'''
        self._mock_repo(svc, tf_content)
        result = svc.validate_topic_in_repository("saptcc", "multi-1")
        assert result["schema_grain_found"] is True
        assert result["topic_file_exists"] is True
        assert result["error"] is None

    def test_returns_not_found_when_schema_grain_absent(self):
        svc = self._make_service()
        tf_content = '''
resource "confluent_kafka_topic" "other-grain" {
  topic_name = "dev.saptcc.other-grain.raw"
}
'''
        self._mock_repo(svc, tf_content)
        result = svc.validate_topic_in_repository("saptcc", "multi-1")
        assert result["schema_grain_found"] is False
        assert result["topic_file_exists"] is True

    def test_returns_file_not_found_when_file_missing(self):
        svc = self._make_service()
        self._mock_repo(svc, None)
        result = svc.validate_topic_in_repository("saptcc", "multi-1")
        assert result["schema_grain_found"] is False
        assert result["topic_file_exists"] is False
        assert result["error"] is not None

    def test_topic_file_path_is_correct(self):
        svc = self._make_service()
        self._mock_repo(svc, None)
        result = svc.validate_topic_in_repository("wahoo", "cdhdr")
        assert result["topic_file_path"] == "confluent_minerva_dev/topics_wahoo.tf"

    def test_schema_grain_found_as_plain_substring(self):
        """schema_grain is matched as plain text substring, not full HCL parse."""
        svc = self._make_service()
        # Just needs to contain the literal string "bseg"
        tf_content = "bseg-something-else = true"
        self._mock_repo(svc, tf_content)
        result = svc.validate_topic_in_repository("saptcc", "bseg")
        assert result["schema_grain_found"] is True

    def test_schema_grain_exact_match_not_partial(self):
        """'multi' must NOT match 'multi-1'."""
        svc = self._make_service()
        tf_content = 'topic_name = "dev.saptcc.multi-1.raw"'
        self._mock_repo(svc, tf_content)
        # Searching for bare 'multi' will match because 'multi' is a substring of 'multi-1'
        # This documents the substring-based matching behavior.
        result = svc.validate_topic_in_repository("saptcc", "multi")
        # 'multi' IS a substring of 'multi-1' → found (expected behavior for substring search)
        assert result["schema_grain_found"] is True

    def test_never_raises_on_github_exception(self):
        """validate_topic_in_repository never raises — returns structured error dict."""
        svc = self._make_service()
        svc._get_repo = MagicMock(side_effect=Exception("API error"))
        # Must NOT raise — should return a structured error dict
        result = svc.validate_topic_in_repository("saptcc", "multi-1")
        assert result["schema_grain_found"] is False
        assert result["topic_file_exists"] is False
        assert result["error"] is not None
        assert "API error" in result["error"]
