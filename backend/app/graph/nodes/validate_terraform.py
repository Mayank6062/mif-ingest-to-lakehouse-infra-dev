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
import logging

logger = logging.getLogger(__name__)


def validate_terraform_node(state: GlueJobState) -> GlueJobState:
    """
    Validates generated Terraform configuration.
    
    Runs:
    - terraform init -backend=false
    - terraform fmt -check -recursive
    - terraform validate
    
    If validation passes: returns state with status='passed', ready to route to create_pr
    If validation fails: returns state with status='failed' + error details, waiting for user
    """
    source_system = state.get("source_system", "unknown")
    job_key = state.get("job_key", "unknown")
    source_exists = state.get("source_system_exists", False)
    
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
        # For EXISTING systems: validate just the HCL entry that will be inserted
        # Store it as a temporary .tf file for terraform validate
        terraform_hcl = state.get("terraform_hcl", "")
        if terraform_hcl:
            terraform_files["job_entry.tf"] = terraform_hcl
    
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
