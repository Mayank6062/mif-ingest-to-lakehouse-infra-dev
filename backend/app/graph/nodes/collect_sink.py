"""
Node: collect_sink
Collects the 3 required sink configuration parameters.
Agent pre-fills values from knowledge base; user can confirm or edit.
"""

from app.graph.state import (
    GlueJobState, STEP_COLLECT_SINK, get_step_number, TOTAL_STEPS
)
from app.agents.knowledge_agent import KnowledgeAgent


def collect_sink_node(state: GlueJobState) -> GlueJobState:
    """
    Presents a 3-field form pre-filled with agent-derived values.
    User can confirm immediately (Continue →) or edit any field inline.
    Fields:
      - iceberg_database   (derived from source system knowledge base)
      - iceberg_warehouse  (derived: s3:// path — must end with /)
      - assume_role_arn    (derived: arn:aws:iam:: ARN)
    NOTE: checkpoint_dir is auto-derived — never user-provided.
    """
    env = state.get("environment", "dev")
    source_system = state.get("source_system", "")

    # ── Agent derives all 3 values from knowledge base ────────────────────
    agent = KnowledgeAgent()
    derived = agent.derive_sink_config(source_system=source_system, environment=env)

    iceberg_database  = derived["iceberg_database"]
    iceberg_warehouse = derived["iceberg_warehouse"]
    assume_role_arn   = derived["assume_role_arn"]

    message = {
        "role": "assistant",
        "content": (
            "I've pre-filled the **sink configuration** from the knowledge base.\n\n"
            "Review the values below — click **Continue →** to proceed, "
            "or hover any row and click ✏️ to edit a value.\n\n"
            "💡 `checkpoint_dir` is auto-set to "
            "`s3://minerva-${local.env}-glue-checkpoints/checkpoints/unified/` — no input needed."
        ),
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_COLLECT_SINK),
            "total": TOTAL_STEPS,
            "label": "Sink Configuration"
        },
        "widget": {
            "type": "form",
            "fields": [
                {
                    "name": "iceberg_database",
                    "label": "Iceberg Database Name",
                    "placeholder": iceberg_database,
                    "default": iceberg_database,
                    "required": True,
                    "field_type": "text",
                    "hint": "AWS Glue catalog database name",
                },
                {
                    "name": "iceberg_warehouse",
                    "label": "Iceberg Warehouse (S3 path)",
                    "placeholder": iceberg_warehouse,
                    "default": iceberg_warehouse,
                    "required": True,
                    "field_type": "text",
                    "hint": "Must start with s3:// and end with /",
                },
                {
                    "name": "assume_role_arn",
                    "label": "IAM Assume Role ARN",
                    "placeholder": assume_role_arn,
                    "default": assume_role_arn,
                    "required": True,
                    "field_type": "text",
                    "hint": "Format: arn:aws:iam::{account_id}:role/{role_name}",
                },
            ],
        },
    }

    return {
        **state,
        "current_step": STEP_COLLECT_SINK,
        "waiting_for_user": True,
        "messages": [message],
    }
