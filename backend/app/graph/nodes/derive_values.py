"""
Node: derive_values
Auto-derives environment, source_system, schema_grain, job_key, kafka_secret_name
from the validated topic. No user input needed — runs immediately.
"""

from app.graph.state import (
    GlueJobState, STEP_DERIVE_VALUES, get_step_number, TOTAL_STEPS
)
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.validation_agent import ValidationAgent


def derive_values_node(state: GlueJobState) -> GlueJobState:
    """
    Derives all values from the topic.
    Also runs initial topic format validation.
    If topic is invalid, sends error and returns to collect_topic.
    """
    from app.graph.state import STEP_COLLECT_TOPIC

    topic = (state.get("topic") or "").strip()

    # First: validate topic format
    validator = ValidationAgent()
    is_valid, err_msg = validator.validate_topic(topic)

    if not is_valid:
        error_message = {
            "role": "assistant",
            "content": (
                f"❌ **Invalid topic format**\n\n{err_msg}\n\n"
                "Please enter the topic again:"
            ),
            "type": "assistant_message",
            "step": {
                "current": get_step_number(STEP_COLLECT_TOPIC),
                "total": TOTAL_STEPS,
                "label": "Enter Kafka Topic"
            },
            "widget": {
                "type": "text_input",
                "placeholder": "dev.saptcc.multi-1.raw",
            },
        }
        return {
            **state,
            "current_step": STEP_COLLECT_TOPIC,
            "waiting_for_user": True,
            "messages": [error_message],
        }

    # Topic is valid — derive all values
    agent = KnowledgeAgent()
    derived = agent.derive_from_topic(topic)

    confirmation_message = {
        "role": "assistant",
        "content": (
            f"✅ **Topic accepted:** `{topic}`\n\n"
            "I've derived the following values automatically:"
        ),
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_DERIVE_VALUES),
            "total": TOTAL_STEPS,
            "label": "Deriving Values"
        },
        "widget": {
            "type": "summary",
            "rows": [
                {"field": "Environment", "value": derived["environment"].upper()},
                {"field": "Source System", "value": derived["source_system"]},
                {"field": "Schema Grain", "value": derived["schema_grain"]},
                {"field": "Job Key", "value": derived["job_key"]},
                {"field": "Kafka Secret Name", "value": derived["kafka_secret_name"]},
            ],
        },
    }

    return {
        **state,
        "current_step": STEP_DERIVE_VALUES,
        "waiting_for_user": False,
        "environment": derived["environment"],
        "source_system": derived["source_system"],
        "schema_grain": derived["schema_grain"],
        "job_key": derived["job_key"],
        "kafka_secret_name": derived["kafka_secret_name"],
        "messages": [confirmation_message],
    }
