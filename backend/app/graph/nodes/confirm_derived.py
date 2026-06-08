"""
Node: confirm_derived
Shows derived values and asks the user to confirm before proceeding.
User can type "yes" to confirm or provide corrections.
"""

from app.graph.state import (
    GlueJobState, STEP_CONFIRM_DERIVED, get_step_number, TOTAL_STEPS
)


def confirm_derived_node(state: GlueJobState) -> GlueJobState:
    """
    Displays a summary of all auto-derived values and asks for confirmation.
    Widget: approval (Yes / No) with option to go back.
    """
    env = state.get("environment", "")
    source_system = state.get("source_system", "")
    schema_grain = state.get("schema_grain", "")
    job_key = state.get("job_key", "")
    kafka_secret = state.get("kafka_secret_name", "")
    source_exists = state.get("source_system_exists", True)
    locals_path = state.get("source_system_locals_path", f"{source_system}/locals.tf")

    folder_status = "✅ Exists in GitHub" if source_exists else "⚠️ New source system"
    folder_action = (
        f"Add new entry to `{locals_path}` (glue.tf unchanged — uses for_each)"
        if source_exists
        else f"Create `{source_system}/locals.tf` and `{source_system}/glue.tf`"
    )

    message = {
        "role": "assistant",
        "content": (
            "Please confirm the derived values before I proceed:\n\n"
            "All values below are **automatically derived** from the topic — "
            "no manual entry needed. If anything looks wrong, click **No** to start over."
        ),
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_CONFIRM_DERIVED),
            "total": TOTAL_STEPS,
            "label": "Confirm Derived Values"
        },
        "widget": {
            "type": "summary",
            "rows": [
                {"field": "Kafka Topic", "value": state.get("topic", "")},
                {"field": "Environment", "value": env.upper()},
                {"field": "Source System", "value": source_system},
                {"field": "Schema Grain", "value": schema_grain},
                {"field": "Job Name", "value": job_key},
                {"field": "Kafka Secret Name", "value": kafka_secret},
                {"field": "Source System Folder", "value": folder_status},
                {"field": "Action", "value": folder_action},
            ],
        },
        "approval_request": True,
        "approval_options": ["✅ Looks correct — continue", "❌ Start over"],
    }

    return {
        **state,
        "current_step": STEP_CONFIRM_DERIVED,
        "waiting_for_user": True,
        "user_confirmed_derived": None,  # reset so stale False from a prior "no" doesn't re-route immediately
        "messages": [message],
    }
