"""
Node: show_summary
Presents the complete configuration summary before Terraform generation.
Auto-runs after successful validation.
"""

from app.graph.state import (
    GlueJobState, STEP_SHOW_SUMMARY, get_step_number, TOTAL_STEPS
)
from app.agents.terraform_agent import TerraformAgent


def show_summary_node(state: GlueJobState) -> GlueJobState:
    """
    Shows a full summary table of all collected values.
    User reviews before Terraform is generated.
    """
    agent = TerraformAgent()
    summary_rows = agent.get_summary_table(state)

    message = {
        "role": "assistant",
        "content": (
            "✅ **Configuration complete!** Here's your full summary.\n\n"
            "Review everything carefully before I generate the Terraform. "
            "If anything is incorrect, type **'restart'** to start over."
        ),
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_SHOW_SUMMARY),
            "total": TOTAL_STEPS,
            "label": "Review Summary"
        },
        "widget": {
            "type": "summary",
            "rows": summary_rows,
        },
    }

    return {
        **state,
        "current_step": STEP_SHOW_SUMMARY,
        "waiting_for_user": False,
        "messages": [message],
    }
