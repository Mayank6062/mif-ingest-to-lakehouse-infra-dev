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
    Runs all validations. Returns updated state with:
    - validation_results: list of all rule results
    - validation_passed: True if no failures
    """
    agent = ValidationAgent()
    results = agent.validate_all(state)
    passed = not agent.has_failures(results)

    failures = [r for r in results if r["result"] == "fail"]
    warnings = [r for r in results if r["result"] == "warn"]
    passes = [r for r in results if r["result"] == "pass"]

    if passed:
        content = (
            f"✅ **All validations passed!** "
            f"({len(passes)} passed, {len(warnings)} warnings)\n\n"
            "Ready to generate the Terraform configuration."
        )
        if warnings:
            content += "\n\n⚠️ **Warnings (non-blocking):**\n"
            for w in warnings:
                content += f"- `{w['rule_id']}` {w['rule_name']}: {w['message']}\n"
    else:
        content = (
            f"❌ **Validation failed** — {len(failures)} error(s) found.\n\n"
            "Please review the errors below and correct your inputs."
        )

    message = {
        "role": "assistant",
        "content": content,
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_RUN_VALIDATION),
            "total": TOTAL_STEPS,
            "label": "Running Validations"
        },
        "widget": {
            "type": "validation",
            "results": results,
        },
    }

    return {
        **state,
        "current_step": STEP_RUN_VALIDATION,
        "waiting_for_user": False,
        "validation_results": results,
        "validation_passed": passed,
        "messages": [message],
    }
