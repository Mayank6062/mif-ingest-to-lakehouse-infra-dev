"""
Node: terraform_preview
Sends the generated Terraform HCL to the frontend for display.
Shows which files will be modified. Then asks for approval.
"""

from app.graph.state import (
    GlueJobState, STEP_TERRAFORM_PREVIEW, STEP_APPROVAL,
    get_step_number, TOTAL_STEPS
)


def terraform_preview_node(state: GlueJobState) -> GlueJobState:
    """
    Sends the Terraform preview to the frontend.
    - EXISTING source system: shows ONE file tab (locals.tf MODIFIED)
      glue.tf is NOT shown because it never changes — for_each handles it automatically.
    - NEW source system: shows TWO file tabs (locals.tf CREATED + glue.tf CREATED)
      Both files go into the PR branch.
    Transitions immediately to approval step.
    """
    terraform_hcl = state.get("terraform_hcl", "")
    locals_tf_full = state.get("locals_tf_full")        # None for existing systems
    glue_tf_content = state.get("glue_tf_content", "")
    files_to_modify = state.get("files_to_modify", [])
    pr_checklist = state.get("pr_checklist", [])
    new_source_checklist = state.get("new_source_checklist")
    source_exists = state.get("source_system_exists", True)
    source_system = state.get("source_system", "")

    # ── Build the locals.tf file entry for the multi-file widget ──────────
    if not source_exists:
        # NEW system: show the full locals.tf content + glue.tf (both CREATED)
        locals_code = locals_tf_full or terraform_hcl
        locals_action = "created"
        locals_label = f"terraform/{source_system}/locals.tf — NEW FILE"
        glue_action = "created"
        glue_label = f"terraform/{source_system}/glue.tf — NEW FILE"
    else:
        # EXISTING system: show only the entry to add inside locals.tf (NO glue.tf tab)
        # glue.tf NEVER changes for existing systems — for_each picks up new jobs automatically
        locals_code = (
            f"# ─── ADD this block inside the existing glue_jobs = {{ ... }} map ───\n"
            f"# File: terraform/{source_system}/locals.tf\n\n"
            f"{terraform_hcl}"
        )
        locals_action = "modified"
        locals_label = f"terraform/{source_system}/locals.tf — MODIFIED"

    files_display = "\n".join([f"- `{f}`" for f in files_to_modify])

    # ── Build message text ─────────────────────────────────────────────────
    if not source_exists:
        content = (
            f"**New source system `{source_system}` — two files will be created:**\n{files_display}\n\n"
            f"- `locals.tf` — complete new file with `ent_func`, `subgroup`, `glue_jobs` map "
            f"and endpoint placeholder maps\n"
            f"- `glue.tf` — standard `module \"glue_jobs\" {{ for_each = local.glue_jobs }}` block\n\n"
            f"Both files go into the PR as new additions."
        )
    else:
        content = (
            f"Here is the Terraform HCL entry to add to `locals.tf`.\n\n"
            f"**File that will be modified:**\n{files_display}\n\n"
            f"`glue.tf` does **not** need changes — `for_each = local.glue_jobs` "
            f"automatically picks up the new entry."
        )

    if not source_exists and new_source_checklist:
        checklist_display = "\n".join([f"- {item}" for item in new_source_checklist])
        content += f"\n\n⚠️ **New source system onboarding required:**\n{checklist_display}"

    # ── Message 1: Multi-file code preview ────────────────────────────────
    code_message = {
        "role": "assistant",
        "content": content,
        "type": "terraform_preview",
        "step": {
            "current": get_step_number(STEP_TERRAFORM_PREVIEW),
            "total": TOTAL_STEPS,
            "label": "Terraform Preview"
        },
        "terraform_hcl": terraform_hcl,
        "files_to_modify": files_to_modify,
        "pr_checklist": pr_checklist,
        "new_source_checklist": new_source_checklist,
        "widget": {
            "type": "code_preview",
            # For NEW systems: both locals.tf (created) + glue.tf (created)
            # For EXISTING systems: only locals.tf (modified) — glue.tf never changes
            "files": (
                [
                    {
                        "filename": f"terraform/{source_system}/locals.tf",
                        "label": locals_label,
                        "language": "hcl",
                        "code": locals_code,
                        "action": locals_action,
                    },
                    {
                        "filename": f"terraform/{source_system}/glue.tf",
                        "label": glue_label,
                        "language": "hcl",
                        "code": glue_tf_content,
                        "action": glue_action,
                    },
                ]
                if not source_exists
                else [
                    {
                        "filename": f"terraform/{source_system}/locals.tf",
                        "label": locals_label,
                        "language": "hcl",
                        "code": locals_code,
                        "action": locals_action,
                    },
                ]
            ),
            # Legacy single-code field (backward compat)
            "language": "hcl",
            "code": terraform_hcl,
        },
    }

    # ── Message 2: Approval request ────────────────────────────────────────
    approval_message = {
        "role": "assistant",
        "content": (
            "🔍 **Review the Terraform above carefully.**\n\n"
            "Do you approve creating a Pull Request with this configuration?\n\n"
            "⚠️ **This will create a GitHub PR in the `mif-ingest-to-lakehouse-infra-dev` repository.**\n"
            "The PR will NOT be merged automatically — a human must review and merge it."
        ),
        "type": "approval_request",
        "step": {
            "current": get_step_number(STEP_APPROVAL),
            "total": TOTAL_STEPS,
            "label": "Awaiting Approval"
        },
        "widget": {
            "type": "approval",
            "options": ["✅ Yes, create Pull Request", "❌ No, cancel"],
        },
    }

    return {
        **state,
        "current_step": STEP_TERRAFORM_PREVIEW,
        "waiting_for_user": True,
        "messages": [code_message, approval_message],
    }
