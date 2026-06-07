"""
Node: generate_terraform
Generates the complete Terraform HCL from the collected state.
Also computes files_to_modify and pr_checklist.
Auto-runs after summary.
"""

from app.graph.state import (
    GlueJobState, STEP_GENERATE_TERRAFORM, get_step_number, TOTAL_STEPS
)
from app.agents.terraform_agent import TerraformAgent
from app.agents.knowledge_agent import KnowledgeAgent


def generate_terraform_node(state: GlueJobState) -> GlueJobState:
    """
    Generates HCL, file list, and PR checklist.
    Sets terraform_hcl, locals_tf_full, glue_tf_content, files_to_modify, pr_checklist in state.
    """
    tf_agent = TerraformAgent()
    kb_agent = KnowledgeAgent()

    # Generate the Terraform HCL job entry block
    terraform_hcl = tf_agent.generate(state)

    # Determine files to modify
    source_system = state.get("source_system", "")
    source_exists = state.get("source_system_exists", True)
    pattern = state.get("source_system_pattern", "local_module")
    job_key = state.get("job_key", "")

    # Generate glue.tf content ONLY for new source systems (it goes into the PR)
    # For EXISTING systems, glue.tf never changes — no need to generate it
    glue_tf_content = tf_agent.get_glue_tf_content(source_system) if not source_exists else None

    # For NEW source systems: generate the FULL locals.tf file (header + entry + endpoints)
    # For EXISTING: None (just the entry block is shown)
    locals_tf_full = tf_agent.generate_full_locals_tf(state) if not source_exists else None

    files_to_modify = kb_agent.get_files_to_modify(source_system, source_exists, pattern)
    pr_checklist = kb_agent.get_pr_checklist(source_system, source_exists, job_key)
    new_source_checklist = (
        kb_agent.get_new_source_checklist(source_system)
        if not source_exists
        else None
    )

    message = {
        "role": "assistant",
        "content": "⚙️ **Terraform configuration generated!** Preview below.",
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_GENERATE_TERRAFORM),
            "total": TOTAL_STEPS,
            "label": "Generating Terraform"
        },
    }

    return {
        **state,
        "current_step": STEP_GENERATE_TERRAFORM,
        "waiting_for_user": False,
        "terraform_hcl": terraform_hcl,
        "locals_tf_full": locals_tf_full,          # None for existing systems
        "glue_tf_content": glue_tf_content or "",  # None → "" for existing systems
        "files_to_modify": files_to_modify,
        "pr_checklist": pr_checklist,
        "new_source_checklist": new_source_checklist,
        "messages": [message],
    }
