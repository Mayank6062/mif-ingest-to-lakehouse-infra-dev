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
    Resolves source-system existence using the live GitHub repository.
    Knowledge-base data is used only for metadata such as display name/pattern.
    """
    source_system = state.get("source_system", "")
    agent = KnowledgeAgent()
    result = agent.check_source_system(source_system)

    exists = result["source_system_exists"]
    pattern = result["source_system_pattern"]
    display = result["source_system_display_name"]
    locals_path = result["source_system_locals_path"]

    if exists:
        status_msg = (
            f"✅ **Source system found in GitHub:** `{locals_path}` exists.\n\n"
            f"**Pattern:** `{pattern}` — I'll update the existing `locals.tf` entry only."
        )
    else:
        status_msg = (
            f"⚠️ **New source system:** `{locals_path}` does not exist in GitHub.\n\n"
            f"I'll create `terraform/{source_system}/locals.tf` and `terraform/{source_system}/glue.tf`."
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
        "knowledge_base_source_system_exists": result["knowledge_base_source_system_exists"],
        "github_source_system_exists": result["github_source_system_exists"],
        "source_system_decision_source": result["source_system_decision_source"],
        "source_system_locals_path": locals_path,
        "messages": [message],
    }
