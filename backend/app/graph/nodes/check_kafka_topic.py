"""
Node: check_kafka_topic
Repository-authoritative topic validation with Kafka as a secondary informational check.

Architecture Freeze Rule — authoritative source:
  The GitHub repository (``confluent_minerva_dev/topics_<source>.tf``) is the
  ONLY authoritative source for determining whether a topic/schema_grain is
  approved and ready for a Glue Job to be created.

  Kafka broker and Schema Registry checks are retained as secondary,
  informational-only checks and NEVER block the workflow.

Business rules (in priority order):

  Rule 1 — repository file absent
            → HARD BLOCK: topic file not found for the source system.
              Show: "Please create the topic first."
              Route back to collect_topic.

  Rule 2 — repository file present but schema_grain not found
            → HARD BLOCK: schema grain not yet declared in the topics file.
              Show: "Please create the topic first."
              Route back to collect_topic.

  Rule 3 — repository file present, schema_grain found
            → PASS: topic is approved. Run secondary Kafka informational checks
              and emit combined status. Route forward (auto_advance=True).

Secondary (informational) Kafka checks — rules below are NON-BLOCKING:
  K1 — Kafka broker unreachable: warn in message, continue.
  K2 — Topic absent from broker: warn in message, continue.
  K3 — Schema Registry unavailable: warn in message, continue.
  K4 — No SR subjects found: warn in message, continue.
  K5 — SR subjects found: confirm in message.

Topic parsing:
  Topic format: ``{env}.{source_system}.{schema_grain}.raw``
  Parts are extracted inline. If parsing fails (< 4 segments), the node
  defers to derive_values to emit the format error.

Interrupt behaviour:
  This node is in interrupt_before. The processor auto-advances for
  auto_advance=True outcomes (Rule 3). For HARD BLOCKs the graph pauses at
  STEP_COLLECT_TOPIC for the user to re-enter a valid topic.
"""

import logging

from app.graph.state import (
    GlueJobState,
    STEP_CHECK_KAFKA_TOPIC,
    STEP_COLLECT_TOPIC,
    get_step_number,
    TOTAL_STEPS,
)
from app.services.kafka_service import KafkaService
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)


def _parse_topic(topic: str) -> tuple[str, str, str] | None:
    """
    Extract (env, source_system, schema_grain) from a topic string.

    Returns None when the topic has fewer than 4 segments — the format error
    is handled downstream by derive_values / ValidationAgent.
    """
    parts = topic.split(".")
    if len(parts) < 4:
        return None
    return parts[0], parts[1], parts[2]


def check_kafka_topic_node(state: GlueJobState) -> GlueJobState:
    """
    Repository-first topic validation.

    Primary check: read confluent_minerva_dev/topics_{source}.tf and search
    for schema_grain.  Only if that passes are secondary Kafka checks run
    (informational only — they never block the workflow).

    Always overwrites all kafka_* and schema_* state fields so that stale
    values from a previous loop iteration do not leak into the current run.
    """
    topic = (state.get("topic") or "").strip()

    step_info = {
        "current": get_step_number(STEP_CHECK_KAFKA_TOPIC),
        "total": TOTAL_STEPS,
        "label": "Checking Kafka Topic",
    }

    # ── Parse topic for source_system / schema_grain ─────────────────────────
    parsed = _parse_topic(topic)
    if parsed is None:
        # Insufficient parts — let derive_values emit the format error.
        # Auto-advance so we don't block here for a malformed topic.
        skip_message = {
            "role": "assistant",
            "content": (
                f"⚠️ **Topic format incomplete:** `{topic}` — "
                "validation skipped. Please ensure the topic follows "
                "`{env}.{source_system}.{schema_grain}.raw` format."
            ),
            "type": "assistant_message",
            "step": step_info,
            "auto_advance": True,
        }
        return {
            **state,
            "current_step": STEP_CHECK_KAFKA_TOPIC,
            "waiting_for_user": False,
            "kafka_topic_exists": None,
            "kafka_topic_missing": False,
            "schema_registry_available": None,
            "schema_count": 0,
            "schema_exists": False,
            "schema_check_needs_approval": False,
            "user_accepted_kafka_check": None,
            "messages": [skip_message],
        }

    _env, source_system, schema_grain = parsed

    # ── PRIMARY: Repository check (AUTHORITATIVE) ─────────────────────────────
    try:
        github_service = GitHubService()
        repo_result = github_service.validate_topic_in_repository(
            source_system=source_system,
            schema_grain=schema_grain,
        )
    except Exception as exc:
        logger.warning(
            "check_kafka_topic_node: GitHub service error during repository "
            "topic validation — treating as blocking. error=%s", exc
        )
        repo_result = {
            "schema_grain_found": False,
            "topic_file_exists": False,
            "topic_file_path": f"confluent_minerva_dev/topics_{source_system}.tf",
            "error": str(exc),
        }

    topic_file_path = repo_result["topic_file_path"]

    # ── Rule 1: topic file does not exist in repository ───────────────────────
    if not repo_result["topic_file_exists"]:
        block_message = {
            "role": "assistant",
            "content": (
                f"🚫 **Topic not found in repository.**\n\n"
                f"The file `{topic_file_path}` does not exist in the base branch.\n\n"
                f"**Please create the topic first**, then return here to create the Glue Job.\n\n"
                f"_Topic:_ `{topic}`"
            ),
            "type": "assistant_message",
            "step": step_info,
        }
        return {
            **state,
            "current_step": STEP_COLLECT_TOPIC,
            "waiting_for_user": True,
            "kafka_topic_exists": None,
            "kafka_topic_missing": True,
            "schema_registry_available": None,
            "schema_count": 0,
            "schema_exists": False,
            "schema_check_needs_approval": False,
            "user_accepted_kafka_check": None,
            "messages": [block_message],
        }

    # ── Rule 2: file exists but schema_grain not found ────────────────────────
    if not repo_result["schema_grain_found"]:
        block_message = {
            "role": "assistant",
            "content": (
                f"🚫 **Schema grain `{schema_grain}` not found in repository.**\n\n"
                f"Searched in `{topic_file_path}` and did not find `{schema_grain}`.\n\n"
                f"**Please create the topic first**, then return here to create the Glue Job.\n\n"
                f"_Topic:_ `{topic}`"
            ),
            "type": "assistant_message",
            "step": step_info,
        }
        return {
            **state,
            "current_step": STEP_COLLECT_TOPIC,
            "waiting_for_user": True,
            "kafka_topic_exists": None,
            "kafka_topic_missing": True,
            "schema_registry_available": None,
            "schema_count": 0,
            "schema_exists": False,
            "schema_check_needs_approval": False,
            "user_accepted_kafka_check": None,
            "messages": [block_message],
        }

    # ── Rule 3: repository approved — run secondary Kafka checks ─────────────
    # Kafka checks are INFORMATIONAL ONLY. Results are reported in the message
    # but never block the workflow.
    kafka_lines: list[str] = []
    kafka_topic_exists: bool | None = None
    schema_registry_available: bool | None = None
    schema_count: int = 0
    schema_exists: bool = False

    try:
        kafka_service = KafkaService()

        # K1/K2: Kafka broker
        topic_found, kafka_error = kafka_service.check_topic_exists(topic)
        kafka_topic_exists = topic_found
        if kafka_error:
            kafka_lines.append(
                f"⚠️ Kafka broker unreachable — {kafka_error} _(informational only)_"
            )
        elif not topic_found:
            kafka_lines.append(
                f"⚠️ Topic `{topic}` not yet found in Kafka broker _(informational only)_"
            )
        else:
            kafka_lines.append(f"✅ Kafka broker: topic `{topic}` confirmed.")

        # K3/K4/K5: Schema Registry
        sr_available, sr_count, sr_error = kafka_service.get_schema_count(topic)
        schema_registry_available = sr_available
        schema_count = sr_count
        schema_exists = sr_count > 0

        if not sr_available:
            kafka_lines.append(
                f"⚠️ Schema Registry unavailable — {sr_error} _(informational only)_"
            )
        elif sr_count == 0:
            kafka_lines.append(
                f"⚠️ No Schema Registry subjects found for `{topic}` _(informational only)_"
            )
        else:
            kafka_lines.append(
                f"✅ Schema Registry: {sr_count} subject(s) found for `{topic}`."
            )
    except Exception as exc:
        logger.warning(
            "check_kafka_topic_node: secondary Kafka check failed (non-blocking). "
            "error=%s", exc
        )
        kafka_lines.append(
            f"⚠️ Kafka/SR checks could not run — {exc} _(informational only)_"
        )

    kafka_section = "\n".join(kafka_lines) if kafka_lines else ""

    info_message = {
        "role": "assistant",
        "content": (
            f"✅ **Topic approved in repository:** `{topic}`\n"
            f"✅ Schema grain `{schema_grain}` found in `{topic_file_path}`.\n\n"
            + (f"**Secondary Kafka checks:**\n{kafka_section}" if kafka_section else "")
        ).strip(),
        "type": "assistant_message",
        "step": step_info,
        "auto_advance": True,
    }

    return {
        **state,
        "current_step": STEP_CHECK_KAFKA_TOPIC,
        "waiting_for_user": False,
        "kafka_topic_exists": kafka_topic_exists,
        "kafka_topic_missing": False,
        "schema_registry_available": schema_registry_available,
        "schema_count": schema_count,
        "schema_exists": schema_exists,
        "schema_check_needs_approval": False,
        "user_accepted_kafka_check": None,
        "messages": [info_message],
    }
