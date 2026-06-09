"""
Integration tests for Kafka check flow in processor + graph.

Requested coverage:
1) STEP_DERIVE_VALUES -> STEP_CHECK_KAFKA_TOPIC -> STEP_CHECK_SOURCE
2) Rule 4 auto_advance processor behavior
3) Rule 2 rejection restart behavior
4) Rule 3 approval continue behavior
"""

import asyncio
import contextlib
from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

import app.graph.builder as _builder_module
from app.graph.builder import build_graph
from app.api.processor import process_first_message, process_user_message
from app.config import get_settings
from app.graph.state import (
    STEP_COLLECT_TOPIC,
    STEP_DERIVE_VALUES,
    STEP_CHECK_KAFKA_TOPIC,
    STEP_CHECK_SOURCE,
    STEP_CONFIRM_DERIVED,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _thread_config(session_id: str) -> dict:
    return {
        "configurable": {"thread_id": session_id},
        "metadata": {"session_id": session_id, "action": "test"},
        "tags": ["test"],
        "run_name": f"test-{session_id}",
    }


@contextlib.contextmanager
def _use_test_graph_and_enabled_flag(enabled: bool = True):
    """Inject test compiled graph singleton and temporary ENABLE_KAFKA_CHECK value."""
    cp = MemorySaver()
    compiled = build_graph(cp)

    settings = get_settings()
    original_flag = settings.enable_kafka_check
    original_graph = _builder_module._compiled_graph
    settings.enable_kafka_check = enabled
    _builder_module._compiled_graph = compiled
    try:
        yield compiled
    finally:
        settings.enable_kafka_check = original_flag
        _builder_module._compiled_graph = original_graph


class TestKafkaIntegrationFlow:
    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_step_chain_derive_to_kafka_to_source(self, mock_check_topic, mock_get_schema):
        """Validate STEP_CHECK_KAFKA_TOPIC -> STEP_DERIVE_VALUES -> STEP_CHECK_SOURCE path."""
        mock_check_topic.return_value = (True, None)
        mock_get_schema.return_value = (False, 0, "Connection refused")  # Rule 3 (approval)

        sid = "it-step-chain"
        with _use_test_graph_and_enabled_flag(enabled=True) as compiled:
            # Session starts at collect_topic
            first_msgs = _run(process_first_message(sid))
            assert first_msgs
            snap0 = _run(compiled.aget_state(_thread_config(sid)))
            assert snap0.values.get("current_step") == STEP_COLLECT_TOPIC

            # Submit topic -> check_kafka_topic should run (now step 2)
            kafka_msgs = _run(process_user_message(sid, "dev.saptcc.multi-1.raw"))
            # Kafka check passes, Rule 3 sends approval_request (no approval yet)
            # Workflow may show a message about topic verified
            snap1 = _run(compiled.aget_state(_thread_config(sid)))
            # After Kafka check, should be ready for derive or awaiting Kafka approval
            assert snap1.values.get("current_step") in {STEP_CHECK_KAFKA_TOPIC, STEP_DERIVE_VALUES}

            # If still at Kafka check (Rule 3 approval), respond with continue
            if snap1.values.get("current_step") == STEP_CHECK_KAFKA_TOPIC:
                derive_msgs = _run(process_user_message(
                    sid,
                    "continue",
                    widget_value={
                        "job_key": "kafka-to-iceberg-batch-saptcc-multi-1",
                        "kafka_secret_name": "minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds",
                    },
                ))
                snap2 = _run(compiled.aget_state(_thread_config(sid)))
                # After Kafka approval, should move to derive_values or check_source
                assert snap2.values.get("current_step") in {STEP_DERIVE_VALUES, STEP_CHECK_SOURCE}

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_rule4_auto_advance_processor_behavior(self, mock_check_topic, mock_get_schema):
        """Rule 4 should auto-continue with no extra user click."""
        mock_check_topic.return_value = (True, None)
        mock_get_schema.return_value = (True, 3, None)  # Rule 4

        sid = "it-rule4-auto"
        with _use_test_graph_and_enabled_flag(enabled=True) as compiled:
            _run(process_first_message(sid))
            _run(process_user_message(sid, "dev.saptcc.multi-1.raw"))

            msgs = _run(process_user_message(
                sid,
                "continue",
                widget_value={
                    "job_key": "kafka-to-iceberg-batch-saptcc-multi-1",
                    "kafka_secret_name": "minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds",
                },
            ))

            # First batch includes Rule 4 info with auto_advance=True
            assert any(m.get("auto_advance") for m in msgs)
            # Processor should immediately append next-node messages (check_source/confirm)
            assert any("Source system" in m.get("content", "") or "Please confirm" in m.get("content", "") for m in msgs)

            # Snapshot should have advanced past check_kafka_topic
            snap = _run(compiled.aget_state(_thread_config(sid)))
            assert snap.values.get("current_step") in {STEP_CHECK_SOURCE, STEP_CONFIRM_DERIVED}

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_rule2_rejection_restart_behavior(self, mock_check_topic, mock_get_schema):
        """Rule 2 NO should clear checkpoint and restart to collect_topic."""
        mock_check_topic.return_value = (True, None)
        mock_get_schema.return_value = (True, 0, None)  # Rule 2

        sid = "it-rule2-reject"
        with _use_test_graph_and_enabled_flag(enabled=True) as compiled:
            _run(process_first_message(sid))
            _run(process_user_message(sid, "dev.saptcc.multi-2.raw"))
            kafka_msgs = _run(process_user_message(
                sid,
                "continue",
                widget_value={
                    "job_key": "kafka-to-iceberg-batch-saptcc-multi-2",
                    "kafka_secret_name": "minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds",
                },
            ))
            assert any(m.get("approval_request") for m in kafka_msgs)

            # Reject at kafka check approval
            restart_msgs = _run(process_user_message(sid, "no"))
            assert any("Welcome" in m.get("content", "") for m in restart_msgs)

            snap = _run(compiled.aget_state(_thread_config(sid)))
            assert snap.values.get("current_step") == STEP_COLLECT_TOPIC

    @patch("app.services.kafka_service.KafkaService.get_schema_count")
    @patch("app.services.kafka_service.KafkaService.check_topic_exists")
    def test_rule3_approval_continue_behavior(self, mock_check_topic, mock_get_schema):
        """Rule 3 YES should continue to check_source/confirm flow."""
        mock_check_topic.return_value = (True, None)
        mock_get_schema.return_value = (False, 0, "Timeout")  # Rule 3

        sid = "it-rule3-continue"
        with _use_test_graph_and_enabled_flag(enabled=True) as compiled:
            _run(process_first_message(sid))
            _run(process_user_message(sid, "dev.saptcc.multi-3.raw"))
            kafka_msgs = _run(process_user_message(
                sid,
                "continue",
                widget_value={
                    "job_key": "kafka-to-iceberg-batch-saptcc-multi-3",
                    "kafka_secret_name": "minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds",
                },
            ))
            assert any(m.get("approval_request") for m in kafka_msgs)

            # Approve continuation
            continue_msgs = _run(process_user_message(sid, "yes"))
            assert any("Source system" in m.get("content", "") or "Please confirm" in m.get("content", "") for m in continue_msgs)

            snap = _run(compiled.aget_state(_thread_config(sid)))
            assert snap.values.get("current_step") in {STEP_CHECK_SOURCE, STEP_CONFIRM_DERIVED}
