"""
Node: run_validation
Runs all business validation rules against the complete state.
Auto-runs. If failures found, goes back to the relevant step.
"""

from app.graph.state import (
    GlueJobState, STEP_RUN_VALIDATION, get_step_number, TOTAL_STEPS
)
from app.agents.validation_agent import ValidationAgent


def run_validation_node(state: GlueJobState) -> GlueJobState:
    """
    Runs all validations silently (internal backend check only).
    Results are stored in state but NOT displayed to user.
    Returns updated state with:
    - validation_results: list of all rule results (not shown in UI)
    - validation_passed: True if no failures
    """
    agent = ValidationAgent()
    results = agent.validate_all(state)
    passed = not agent.has_failures(results)

    # Validations run internally but messages are NOT sent to UI
    # This allows the workflow to route based on validation_passed without showing details
    
    return {
        **state,
        "current_step": STEP_RUN_VALIDATION,
        "waiting_for_user": False,
        "validation_results": results,
        "validation_passed": passed,
        "messages": [],  # Hidden from UI — validation runs internally
    }
