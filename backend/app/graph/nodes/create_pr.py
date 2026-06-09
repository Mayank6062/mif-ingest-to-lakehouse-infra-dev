"""
Node: create_pr
Creates the GitHub Pull Request. Only runs after user_approved == True.
This is the ONLY place where the PR is created — never anywhere else.
"""

from app.graph.state import (
    GlueJobState, STEP_CREATE_PR, STEP_PR_SUCCESS,
    get_step_number, TOTAL_STEPS
)
from app.services.audit_log import log_event
from app.services.github_service import GitHubService


def create_pr_node(state: GlueJobState) -> GlueJobState:
    """
    Creates the GitHub PR.
    CRITICAL SAFETY CHECKS:
    - user_approved must be True
    - terraform_validation_status must be "passed"
    """
    # Safety guard 1: user approval check
    if not state.get("user_approved"):
        error_msg = {
            "role": "assistant",
            "content": "❌ **Error:** PR creation blocked — user approval not confirmed.",
            "type": "error",
        }
        return {
            **state,
            "current_step": STEP_CREATE_PR,
            "waiting_for_user": False,
            "messages": [error_msg],
        }

    # Safety guard 2: terraform validation check (hard gate)
    if state.get("terraform_validation_status") != "passed":
        error_msg = {
            "role": "assistant",
            "content": (
                "❌ **Error:** PR creation blocked — Terraform validation did not pass.\n\n"
                f"Validation Status: {state.get('terraform_validation_status', 'unknown')}\n\n"
                "All Terraform validations must pass before creating a Pull Request."
            ),
            "type": "error",
        }
        return {
            **state,
            "current_step": STEP_CREATE_PR,
            "waiting_for_user": False,
            "messages": [error_msg],
        }

    # Set branch name before PR creation
    svc = GitHubService()
    source_system = state.get("source_system", "")
    schema_grain = state.get("schema_grain", "")
    branch_name = state.get("branch_name") or svc.make_branch_name(source_system, schema_grain)

    # Update state with branch name first
    updated_state = {**state, "branch_name": branch_name}

    log_event("approval_received", "user", updated_state)

    try:
        log_event("pr_creation_started", "system", updated_state)
        # Creating PR message while working
        working_message = {
            "role": "assistant",
            "content": (
                f"🔄 **Creating Pull Request...**\n\n"
                f"Branch: `{branch_name}`"
            ),
            "type": "assistant_message",
            "step": {
                "current": get_step_number(STEP_CREATE_PR),
                "total": TOTAL_STEPS,
                "label": "Creating Pull Request"
            },
        }

        pr_result = svc.create_pr(updated_state)
        log_event("pr_creation_succeeded", "system", updated_state,
                  pr_number=pr_result["pr_number"], pr_url=pr_result["pr_url"])

        success_message = {
            "role": "assistant",
            "content": (
                f"🎉 **Pull Request created successfully!**\n\n"
                f"**PR #{pr_result['pr_number']}:** [{pr_result['pr_url']}]({pr_result['pr_url']})\n"
                f"**Branch:** `{pr_result['branch_name']}`\n\n"
                f"The PR is ready for review. "
                f"It will NOT be auto-merged — a team member must review and approve it."
            ),
            "type": "pr_created",
            "step": {
                "current": get_step_number(STEP_PR_SUCCESS),
                "total": TOTAL_STEPS,
                "label": "Pull Request Created"
            },
            "pr_url": pr_result["pr_url"],
            "branch_name": pr_result["branch_name"],
            "widget": {
                "type": "pr_success",
                "pr_url": pr_result["pr_url"],
                "branch_name": pr_result["branch_name"],
                "files_modified": pr_result.get("files_modified", []),
            },
        }

        return {
            **updated_state,
            "current_step": STEP_PR_SUCCESS,
            "waiting_for_user": False,
            "pr_url": pr_result["pr_url"],
            "branch_name": pr_result["branch_name"],
            "pr_number": pr_result["pr_number"],
            "messages": [working_message, success_message],
        }

    except Exception as exc:
        log_event("pr_creation_failed", "system", updated_state, error=str(exc))
        error_message = {
            "role": "assistant",
            "content": (
                f"❌ **Failed to create Pull Request**\n\n"
                f"Error: `{str(exc)}`\n\n"
                f"Please check your GitHub token and repository settings in the `.env` file, "
                f"then try again."
            ),
            "type": "error",
            "step": {
                "current": get_step_number(STEP_CREATE_PR),
                "total": TOTAL_STEPS,
                "label": "PR Creation Failed"
            },
        }
        return {
            **updated_state,
            "current_step": STEP_CREATE_PR,
            "waiting_for_user": False,
            "error_message": str(exc),
            "messages": [error_message],
        }
