"""
Node: validate_terraform
Validates generated Terraform configuration before PR creation.
Runs: terraform init, terraform fmt -check, terraform validate
Blocks PR creation if validation fails.
"""

from app.graph.state import (
    GlueJobState, STEP_VALIDATE_TERRAFORM, STEP_CREATE_PR,
    get_step_number, TOTAL_STEPS
)
from app.services.terraform_validator import TerraformValidator
from app.services.audit_log import log_event
from app.config import get_settings
import logging
from importlib import import_module

logger = logging.getLogger(__name__)


def validate_terraform_node(state: GlueJobState) -> GlueJobState:
    """
    Validates generated Terraform configuration.
    
    Runs:
    - terraform init -backend=false
    - terraform fmt -check -recursive
    - terraform validate
    
    If ENABLE_TERRAFORM_PLAN=false (default for local dev), skips all binary
    checks and auto-passes so the workflow proceeds to PR creation.

    If validation passes: returns state with status='passed', ready to route to create_pr
    If validation fails: returns state with status='failed' + error details, waiting for user
    """
    source_system = state.get("source_system", "unknown")
    job_key = state.get("job_key", "unknown")
    source_exists = state.get("source_system_exists", False)

    settings = get_settings()

    # ── Skip terraform binary checks when ENABLE_TERRAFORM_PLAN=false ────────
    if not settings.enable_terraform_plan:
        logger.info(f"[{source_system}] Terraform validation skipped (ENABLE_TERRAFORM_PLAN=false)")
        skip_message = {
            "role": "assistant",
            "content": (
                "⏭️ **Terraform validation skipped** (`ENABLE_TERRAFORM_PLAN=false`)\n\n"
                "Set `ENABLE_TERRAFORM_PLAN=true` in `.env` with cloud credentials "
                "to enable `terraform init / fmt / validate` checks.\n\n"
                "Proceeding to PR creation..."
            ),
            "type": "assistant_message",
            "step": {
                "current": get_step_number(STEP_VALIDATE_TERRAFORM),
                "total": TOTAL_STEPS,
                "label": "Validating Terraform"
            },
        }
        return {
            **state,
            "current_step": STEP_VALIDATE_TERRAFORM,
            "waiting_for_user": False,
            "terraform_validation_status": "passed",
            "terraform_validation_logs": "Skipped — ENABLE_TERRAFORM_PLAN=false",
            "terraform_validation_errors": "",
            "messages": [skip_message],
        }

    logger.info(f"[{source_system}] Starting Terraform validation")
    log_event("terraform_validation_started", "system", state)

    # Collect all Terraform files
    terraform_files = {}
    
    # For NEW source systems: validate full locals.tf and glue.tf
    if not source_exists:
        if state.get("locals_tf_full"):
            terraform_files["locals.tf"] = state.get("locals_tf_full", "")
        
        if state.get("glue_tf_content"):
            terraform_files["glue.tf"] = state.get("glue_tf_content", "")
    else:
        # For EXISTING systems: fetch the repository's locals.tf, merge the
        # generated job entry into it exactly as `create_pr` would, and include
        # any glue.tf required for validation context.
        terraform_hcl = state.get("terraform_hcl", "")
        gh_mod = import_module("app.services.github_service")
        GitHubService = gh_mod.GitHubService
        _insert_into_glue_jobs = gh_mod._insert_into_glue_jobs
        svc = GitHubService()
        # Determine repo path for locals.tf
        try:
            repo_state = svc.get_source_system_repository_state(source_system)
            locals_path = repo_state.get("locals_path")
            repo = svc._get_repo()
            base_file = svc._get_file_content(repo, locals_path, svc._base_branch)
        except Exception as e:
            logger.error(f"[{source_system}] Failed to fetch repository files: {e}")
            error_msg = {
                "role": "assistant",
                "content": (
                    "❌ **Terraform Validation Error**\n\n"
                    "Could not read existing locals.tf from the repository. "
                    "Please verify the repository and try again."
                ),
                "type": "error",
            }
            return {
                **state,
                "current_step": STEP_VALIDATE_TERRAFORM,
                "waiting_for_user": True,
                "terraform_validation_status": "failed",
                "terraform_validation_logs": "",
                "terraform_validation_errors": str(e),
                "messages": [error_msg],
            }

        if base_file is None:
            logger.error(f"[{source_system}] locals.tf not found at {locals_path}")
            error_msg = {
                "role": "assistant",
                "content": (
                    "❌ **Terraform Validation Error**\n\n"
                    "Repository locals.tf could not be found. Ensure the repository "
                    "contains the expected file before validating."
                ),
                "type": "error",
            }
            return {
                **state,
                "current_step": STEP_VALIDATE_TERRAFORM,
                "waiting_for_user": True,
                "terraform_validation_status": "failed",
                "terraform_validation_logs": "",
                "terraform_validation_errors": f"Missing file: {locals_path}",
                "messages": [error_msg],
            }

        # Merge the generated entry into the fetched locals.tf
        current_content = base_file.decoded_content.decode("utf-8")
        try:
            merged = _insert_into_glue_jobs(current_content, terraform_hcl)
        except Exception as exc:
            logger.error(f"[{source_system}] Failed to merge job entry: {exc}")
            error_msg = {
                "role": "assistant",
                "content": (
                    "❌ **Terraform Validation Error**\n\n"
                    "Failed to insert job entry into existing locals.tf: " + str(exc)
                ),
                "type": "error",
            }
            return {
                **state,
                "current_step": STEP_VALIDATE_TERRAFORM,
                "waiting_for_user": True,
                "terraform_validation_status": "failed",
                "terraform_validation_logs": "",
                "terraform_validation_errors": str(exc),
                "messages": [error_msg],
            }

        terraform_files["locals.tf"] = merged

        # Optionally include glue.tf from the same directory or root for context
        # Try {source}/glue.tf then glue.tf at repo root
        try:
            glue_path_candidate = f"{source_system}/glue.tf"
            glue_file = svc._get_file_content(repo, glue_path_candidate, svc._base_branch)
            if glue_file is None:
                glue_file = svc._get_file_content(repo, "glue.tf", svc._base_branch)
            if glue_file is not None:
                terraform_files["glue.tf"] = glue_file.decoded_content.decode("utf-8")
        except Exception:
            # Non-fatal: validation can proceed without glue.tf if unavailable
            logger.debug(f"[{source_system}] glue.tf not found or could not be read; continuing")
    
    # If no files to validate, return error
    if not terraform_files:
        error_msg = {
            "role": "assistant",
            "content": (
                "❌ **Terraform Validation Error**\n\n"
                "No Terraform content was generated. Please go back and regenerate the configuration."
            ),
            "type": "error",
        }
        logger.error(f"[{source_system}] No Terraform content to validate")
        return {
            **state,
            "current_step": STEP_VALIDATE_TERRAFORM,
            "waiting_for_user": True,
            "terraform_validation_status": "failed",
            "terraform_validation_logs": "No Terraform content generated",
            "terraform_validation_errors": "Missing terraform_hcl or glue_tf_content",
            "messages": [error_msg],
        }

    # Run validation
    validator = TerraformValidator()
    result = validator.validate(terraform_files, source_system)

    # Store validation results in state
    state_update = {
        **state,
        "current_step": STEP_VALIDATE_TERRAFORM,
        "terraform_validation_status": result["status"],
        "terraform_validation_logs": result["logs"],
        "terraform_validation_errors": result["errors"],
        "terraform_validation_diagnostics": result.get("terraform_validation_diagnostics", []),
    }

    if result["status"] == "passed":
        logger.info(f"[{source_system}] ✅ Terraform validation passed")
        log_event("terraform_validation_passed", "system", state_update)

        # Success message
        message = {
            "role": "assistant",
            "content": (
                f"✅ **Terraform Validation Passed**\n\n"
                f"All validations completed successfully:\n"
                f"- `terraform init -backend=false` ✓\n"
                f"- `terraform fmt -check -recursive` ✓\n"
                f"- `terraform validate` ✓\n\n"
                f"Proceeding to PR creation..."
            ),
            "type": "assistant_message",
            "step": {
                "current": get_step_number(STEP_VALIDATE_TERRAFORM),
                "total": TOTAL_STEPS,
                "label": "Validating Terraform"
            },
        }

        return {
            **state_update,
            "waiting_for_user": False,
            "messages": [message],
        }

    else:
        # Validation failed
        logger.error(f"[{source_system}] ❌ Terraform validation failed (command: {result['failed_command']})")
        log_event("terraform_validation_failed", "system", state_update)

        # Error message with detailed output
        error_content = (
            f"❌ **Terraform Validation Failed**\n\n"
            f"**Failed Command:** `{result['failed_command']}`\n\n"
            f"**Validation Output:**\n"
            f"```\n{result['logs']}\n```\n\n"
        )

        if result["errors"]:
            error_content += (
                f"**Errors:**\n"
                f"```\n{result['errors']}\n```\n\n"
            )

        error_content += (
            f"**Action Required:**\n"
            f"• Review the validation errors above\n"
            f"• Go back to fix the configuration issues\n"
            f"• Regenerate the Terraform files\n"
            f"\n"
            f"Type **'restart'** to start a new Glue job or **'back'** to review your configuration."
        )

        error_message = {
            "role": "assistant",
            "content": error_content,
            "type": "error",
        }

        return {
            **state_update,
            "waiting_for_user": True,
            "messages": [error_message],
        }
