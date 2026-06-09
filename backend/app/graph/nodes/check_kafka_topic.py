"""
Node: check_kafka_topic
Validates Kafka topic existence and Schema Registry schema presence.

Implements four business rules:

  Rule 1 — topic absent from Kafka broker
            → error message, route back to collect_topic (no approval)

  Rule 2 — topic present, SR available, zero matching subjects
            → approval dialog: "No schema found — continue anyway?"

  Rule 3 — topic present, Schema Registry unavailable (any connection error)
            → approval dialog: "SR unavailable — continue anyway?"

  Rule 4 — topic present, one or more matching subjects found
            → info message with auto_advance=True (processor auto-resumes)

Schema matching rule:  subject.startswith(topic + "-")

Interrupt behaviour:
  This node IS in interrupt_before so that derive_values can present its form
  first (user fills job_key / kafka_secret_name), then this node runs.
  For Rules 2/3 the graph pauses again at interrupt_before=STEP_CHECK_SOURCE,
  letting the user respond to the approval dialog.
  For Rule 4 the processor detects auto_advance=True and immediately resumes —
  no extra user click is required.
"""

from app.graph.state import (
    GlueJobState,
    STEP_CHECK_KAFKA_TOPIC,
    STEP_COLLECT_TOPIC,
    get_step_number,
    TOTAL_STEPS,
)
from app.services.kafka_service import KafkaService


def check_kafka_topic_node(state: GlueJobState) -> GlueJobState:
    """
    Runs Kafka + Schema Registry validation and applies Rules 1–4.

    Always overwrites all kafka_* and schema_* state fields so that stale
    values from a previous loop iteration do not leak into the current run.
    """
    topic = (state.get("topic") or "").strip()
    service = KafkaService()

    step_info = {
        "current": get_step_number(STEP_CHECK_KAFKA_TOPIC),
        "total": TOTAL_STEPS,
        "label": "Checking Kafka Topic",
    }

    # ── Kafka topic existence ────────────────────────────────────────────────
    topic_found, kafka_error = service.check_topic_exists(topic)

    if not topic_found:
        # ── Rule 1: topic missing (or broker unreachable) ────────────────────
        detail = f"\n\n_Broker error: {kafka_error}_" if kafka_error else ""
        error_message = {
            "role": "assistant",
            "content": (
                f"❌ **Topic not found in Kafka:** `{topic}`\n\n"
                f"Please verify the topic exists in the Kafka broker and try again."
                f"{detail}"
            ),
            "type": "assistant_message",
            "step": step_info,
        }
        return {
            **state,
            "current_step": STEP_COLLECT_TOPIC,
            "waiting_for_user": True,
            "kafka_topic_exists": False,
            "kafka_topic_missing": True,
            "schema_registry_available": None,
            "schema_count": 0,
            "schema_exists": False,
            "schema_check_needs_approval": False,
            "user_accepted_kafka_check": None,
            "messages": [error_message],
        }

    # ── Schema Registry check ────────────────────────────────────────────────
    sr_available, schema_count, sr_error = service.get_schema_count(topic)

    if sr_available and schema_count == 0:
        # ── Rule 2: topic found, SR available, no matching subjects ──────────
        approval_message = {
            "role": "assistant",
            "content": (
                f"✅ **Topic found:** `{topic}`\n\n"
                f"⚠️ **No Schema Registry subjects** were found matching this topic.\n\n"
                f"Matching rule: subjects must begin with `{topic}-`\n\n"
                f"Do you want to continue creating the Glue Job anyway?"
            ),
            "type": "assistant_message",
            "step": step_info,
            "approval_request": True,
            "approval_options": ["Yes, Continue", "No, Cancel"],
        }
        return {
            **state,
            "current_step": STEP_CHECK_KAFKA_TOPIC,
            "waiting_for_user": True,
            "kafka_topic_exists": True,
            "kafka_topic_missing": False,
            "schema_registry_available": True,
            "schema_count": 0,
            "schema_exists": False,
            "schema_check_needs_approval": True,
            "user_accepted_kafka_check": None,
            "messages": [approval_message],
        }

    if not sr_available:
        # ── Rule 3: topic found, Schema Registry unavailable ─────────────────
        approval_message = {
            "role": "assistant",
            "content": (
                f"✅ **Topic found:** `{topic}`\n\n"
                f"⚠️ **Schema Registry is currently unavailable** — "
                f"schema existence cannot be verified.\n\n"
                f"_Error: {sr_error}_\n\n"
                f"Do you want to continue creating the Glue Job anyway?"
            ),
            "type": "assistant_message",
            "step": step_info,
            "approval_request": True,
            "approval_options": ["Yes, Continue", "No, Cancel"],
        }
        return {
            **state,
            "current_step": STEP_CHECK_KAFKA_TOPIC,
            "waiting_for_user": True,
            "kafka_topic_exists": True,
            "kafka_topic_missing": False,
            "schema_registry_available": False,
            "schema_count": 0,
            "schema_exists": False,
            "schema_check_needs_approval": True,
            "user_accepted_kafka_check": None,
            "messages": [approval_message],
        }

    # ── Rule 4: topic found, schema subjects > 0 ────────────────────────────
    # auto_advance=True signals processor.py to immediately resume the graph
    # without waiting for user input (no approval dialog required).
    info_message = {
        "role": "assistant",
        "content": (
            f"✅ **Topic verified:** `{topic}`\n"
            f"✅ **Schema Registry verified:** {schema_count} matching "
            f"subject(s) found."
        ),
        "type": "assistant_message",
        "step": step_info,
        "auto_advance": True,
    }
    return {
        **state,
        "current_step": STEP_CHECK_KAFKA_TOPIC,
        "waiting_for_user": False,
        "kafka_topic_exists": True,
        "kafka_topic_missing": False,
        "schema_registry_available": True,
        "schema_count": schema_count,
        "schema_exists": True,
        "schema_check_needs_approval": False,
        "user_accepted_kafka_check": None,
        "messages": [info_message],
    }
