"""
Node: check_source_system
Checks whether the source system folder already exists in the repository.
Auto-runs, no user input. Sets source_system_exists, pattern_type.
"""

from app.graph.state import (
    GlueJobState, STEP_CHECK_SOURCE, get_step_number, TOTAL_STEPS
)
from app.agents.knowledge_agent import KnowledgeAgent


def check_source_system_node(state: GlueJobState) -> GlueJobState:
    """
    Looks up the source system in source_systems.json.
    Determines if the folder exists and what pattern it uses.
    """
    source_system = state.get("source_system", "")
    agent = KnowledgeAgent()
    result = agent.check_source_system(source_system)

    exists = result["source_system_exists"]
    pattern = result["source_system_pattern"]
    display = result["source_system_display_name"]

    if exists:
        status_msg = (
            f"✅ **Source system found:** `{source_system}/`\n\n"
            f"**Pattern:** `{pattern}` — I'll update the existing "
            f"`locals.tf` and `glue.tf` files."
        )
    else:
        status_msg = (
            f"⚠️ **New source system:** `{source_system}` is not in the known systems list.\n\n"
            f"I'll create the `terraform/{source_system}/` folder with "
            f"`locals.tf` and `glue.tf`, and register it in `.vela.py`."
        )

    message = {
        "role": "assistant",
        "content": status_msg,
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_CHECK_SOURCE),
            "total": TOTAL_STEPS,
            "label": "Source System Check"
        },
    }

    return {
        **state,
        "current_step": STEP_CHECK_SOURCE,
        "waiting_for_user": False,
        "source_system_exists": exists,
        "source_system_pattern": pattern,
        "source_system_display_name": display,
        "messages": [message],
    }
