"""
Node: collect_topic
Sends the opening greeting and asks for the Kafka topic.
This is always the first node. It sets waiting_for_user=True.
"""

from app.graph.state import (
    GlueJobState, STEP_COLLECT_TOPIC, STEP_DERIVE_VALUES,
    get_step_number, TOTAL_STEPS
)
from app.knowledge.loader import get_knowledge_base


def collect_topic_node(state: GlueJobState) -> GlueJobState:
    """
    Emits the welcome message and asks for the Kafka topic.
    Widget: text_input with regex hint.
    """
    kb = get_knowledge_base()
    topic_regex = kb.topic_regex
    envs = kb.allowed_environments

    greeting = (
        "👋 Welcome to the **MIF Glue Job Creator**!\n\n"
        "I'll guide you through creating a production-ready Terraform entry "
        "for a new AWS Glue job in the `mif-ingest-to-lakehouse-infra-dev` repository.\n\n"
        "Let's start with the Kafka topic name.\n\n"
        "**Format:** `{env}.{source_system}.{schema_grain}.raw`\n"
        f"**Allowed envs:** `{', '.join(envs)}`\n"
        "**Example:** `dev.saptcc.multi-1.raw`"
    )

    message = {
        "role": "assistant",
        "content": greeting,
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_COLLECT_TOPIC),
            "total": TOTAL_STEPS,
            "label": "Enter Kafka Topic"
        },
        "widget": {
            "type": "text_input",
            "placeholder": "dev.saptcc.multi-1.raw",
            "hint": f"Must match: {topic_regex}",
        },
    }

    return {
        **state,
        "current_step": STEP_COLLECT_TOPIC,
        "waiting_for_user": True,
        "messages": [message],
    }
