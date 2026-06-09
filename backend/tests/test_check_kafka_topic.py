"""
Unit tests for check_kafka_topic_node — covers all four business rules.

Mocking strategy:
  - KafkaService.check_topic_exists is patched at the class level so tests
    are independent of a live Kafka broker.
  - KafkaService.get_schema_count is patched similarly for Schema Registry.

Test cases:
  A) Rule 1 — topic missing          → error message, route to collect_topic
  B) Rule 2 — no schema (SR up)      → approval dialog
  C) Rule 3 — SR unavailable         → approval dialog
  D) Rule 4 — schema found           → info + auto_advance, no approval
"""

import pytest
from unittest.mock import patch, MagicMock

from app.graph.state import (
    STEP_COLLECT_TOPIC,
    STEP_CHECK_KAFKA_TOPIC,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# A) Rule 1 — Topic missing in Kafka
# ─────────────────────────────────────────────────────────────────────────────

class TestRule1TopicMissing:
    """Topic absent from Kafka broker → hard block, return to topic entry."""

    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_returns_error_message(self, mock_check):
        mock_check.return_value = (False, None)
        result = _run_node(_base_state("dev.saptcc.multi-999.raw"))
        msgs = result["messages"]
        assert len(msgs) == 1
        assert "not found" in msgs[0]["content"].lower()
        assert "dev.saptcc.multi-999.raw" in msgs[0]["content"]

    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_routes_to_collect_topic(self, mock_check):
        mock_check.return_value = (False, None)
        result = _run_node(_base_state("dev.saptcc.multi-999.raw"))
        assert result["current_step"] == STEP_COLLECT_TOPIC

    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_sets_kafka_topic_missing_flag(self, mock_check):
        mock_check.return_value = (False, None)
        result = _run_node(_base_state("dev.saptcc.multi-999.raw"))
        assert result["kafka_topic_exists"] is False
        assert result["kafka_topic_missing"] is True

    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_no_approval_dialog(self, mock_check):
        mock_check.return_value = (False, None)
        result = _run_node(_base_state("dev.saptcc.multi-999.raw"))
        msg = result["messages"][0]
        assert not msg.get("approval_request")
        assert "approval_options" not in msg

    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_no_auto_advance(self, mock_check):
        mock_check.return_value = (False, None)
        result = _run_node(_base_state("dev.saptcc.multi-999.raw"))
        assert not result["messages"][0].get("auto_advance")

    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_broker_error_message_included(self, mock_check):
        mock_check.return_value = (False, "Connection refused")
        result = _run_node(_base_state("dev.saptcc.multi-999.raw"))
        assert "Connection refused" in result["messages"][0]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# B) Rule 2 — Topic present, SR available, schema count = 0
# ─────────────────────────────────────────────────────────────────────────────

class TestRule2NoSchema:
    """Schema Registry available but zero matching subjects → approval dialog."""

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_sends_approval_dialog(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 0, None)  # SR up, zero subjects
        result = _run_node(_base_state("dev.saptcc.multi-2.raw"))
        msg = result["messages"][0]
        assert msg.get("approval_request") is True
        assert "Yes, Continue" in msg["approval_options"]
        assert "No, Cancel" in msg["approval_options"]

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_current_step_is_check_kafka_topic(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-2.raw"))
        assert result["current_step"] == STEP_CHECK_KAFKA_TOPIC

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_sets_schema_check_needs_approval(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-2.raw"))
        assert result["schema_check_needs_approval"] is True
        assert result["schema_registry_available"] is True
        assert result["schema_count"] == 0
        assert result["schema_exists"] is False

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_message_mentions_topic(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-2.raw"))
        assert "dev.saptcc.multi-2.raw" in result["messages"][0]["content"]

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_no_auto_advance(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 0, None)
        result = _run_node(_base_state("dev.saptcc.multi-2.raw"))
        assert not result["messages"][0].get("auto_advance")


# ─────────────────────────────────────────────────────────────────────────────
# C) Rule 3 — Topic present, Schema Registry unavailable
# ─────────────────────────────────────────────────────────────────────────────

class TestRule3SRUnavailable:
    """SR connection fails → approval dialog regardless of actual schema state."""

    @pytest.mark.parametrize("error_msg", [
        "Connection refused",
        "timed out",
        "503 Service Unavailable",
        "Name or service not known",
    ])
    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_sends_approval_dialog_for_all_sr_errors(
        self, mock_check, mock_schema, error_msg
    ):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (False, 0, error_msg)
        result = _run_node(_base_state("dev.saptcc.multi-3.raw"))
        msg = result["messages"][0]
        assert msg.get("approval_request") is True
        assert "Yes, Continue" in msg["approval_options"]
        assert "No, Cancel" in msg["approval_options"]

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_sets_sr_unavailable_in_state(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (False, 0, "Connection refused")
        result = _run_node(_base_state("dev.saptcc.multi-3.raw"))
        assert result["schema_registry_available"] is False
        assert result["schema_check_needs_approval"] is True

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_error_text_in_message(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (False, 0, "timed out after 5s")
        result = _run_node(_base_state("dev.saptcc.multi-3.raw"))
        assert "timed out after 5s" in result["messages"][0]["content"]

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_no_auto_advance(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (False, 0, "503")
        result = _run_node(_base_state("dev.saptcc.multi-3.raw"))
        assert not result["messages"][0].get("auto_advance")


# ─────────────────────────────────────────────────────────────────────────────
# D) Rule 4 — Topic present, schema count > 0
# ─────────────────────────────────────────────────────────────────────────────

class TestRule4SchemaFound:
    """One or more matching subjects → info message + auto_advance, no dialog."""

    @pytest.mark.parametrize("count", [1, 2, 5, 100])
    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_auto_advance_for_any_positive_count(self, mock_check, mock_schema, count):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, count, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["messages"][0].get("auto_advance") is True

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_no_approval_dialog(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 3, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        msg = result["messages"][0]
        assert not msg.get("approval_request")
        assert "approval_options" not in msg

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_sets_schema_exists_true(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 3, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["schema_exists"] is True
        assert result["schema_count"] == 3
        assert result["schema_registry_available"] is True
        assert result["kafka_topic_exists"] is True
        assert result["kafka_topic_missing"] is False

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_current_step_is_check_kafka_topic(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 2, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["current_step"] == STEP_CHECK_KAFKA_TOPIC

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_schema_count_in_message_content(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 4, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert "4" in result["messages"][0]["content"]

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_waiting_for_user_is_false(self, mock_check, mock_schema):
        mock_check.return_value = (True, None)
        mock_schema.return_value = (True, 1, None)
        result = _run_node(_base_state("dev.saptcc.multi-1.raw"))
        assert result["waiting_for_user"] is False


# ─────────────────────────────────────────────────────────────────────────────
# E) KafkaService prefix-matching logic
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaRegistryPrefixMatching:
    """Validate the prefix-match rule in KafkaService.get_schema_count."""

    @patch("httpx.get")
    def test_matches_hyphen_prefixed_subjects(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            "dev.saptcc.multi-1.raw-obj_1",
            "dev.saptcc.multi-1.raw-obj_2",
            "dev.saptcc.multi-1.raw-customer",
            "dev.saptcc.multi-1.raw-value",
        ]
        mock_get.return_value = mock_response

        from app.services.kafka_service import KafkaService
        svc = KafkaService()
        available, count, err = svc.get_schema_count("dev.saptcc.multi-1.raw")
        assert available is True
        assert count == 4
        assert err is None

    @patch("httpx.get")
    def test_rejects_non_hyphen_subjects(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            "dev.saptcc.multi-1.raw",           # exact match — no hyphen suffix
            "dev.saptcc.multi-1",               # shorter, no suffix
            "dev.saptcc.multi-1.rawextra",      # no hyphen separator
            "dev.saptcc.multi-2.raw-obj_1",     # different topic
        ]
        mock_get.return_value = mock_response

        from app.services.kafka_service import KafkaService
        svc = KafkaService()
        available, count, err = svc.get_schema_count("dev.saptcc.multi-1.raw")
        assert available is True
        assert count == 0

    @patch("httpx.get")
    def test_empty_registry_returns_zero(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        from app.services.kafka_service import KafkaService
        svc = KafkaService()
        available, count, err = svc.get_schema_count("dev.saptcc.multi-1.raw")
        assert available is True
        assert count == 0

    @patch("httpx.get", side_effect=Exception("Connection refused"))
    def test_connection_error_returns_unavailable(self, _mock_get):
        from app.services.kafka_service import KafkaService
        svc = KafkaService()
        available, count, err = svc.get_schema_count("dev.saptcc.multi-1.raw")
        assert available is False
        assert count == 0
        assert "Connection refused" in err
