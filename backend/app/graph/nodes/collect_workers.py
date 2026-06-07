"""
Node: collect_workers
Collects worker configuration with smart defaults pre-selected.
Uses chip selectors and dropdowns — almost everything has a default.
"""

from app.graph.state import (
    GlueJobState, STEP_COLLECT_WORKERS, get_step_number, TOTAL_STEPS
)
from app.knowledge.loader import get_knowledge_base


def collect_workers_node(state: GlueJobState) -> GlueJobState:
    """
    Presents worker config form with defaults pre-filled.
    User can accept defaults (one click) or override any field.
    Defaults (saptcc standard):
      - worker_type: G.2X
      - number_of_workers: 4
      - job_type: unified
      - job_version: 0.3.0
      - glue_version: 5.1  (confirmed from saptcc/locals.tf)
      - ent_func: shown only for NEW source systems (file-level local)
      - subgroup: shown only for NEW source systems (file-level local)
      - scheduling_mode: manual
    """
    kb = get_knowledge_base()
    defaults = kb.defaults
    allowed_worker_types = kb.allowed_worker_types
    allowed_ent_funcs = kb.allowed_enterprise_funcs
    allowed_job_types = kb.allowed_job_types
    source_system_exists = state.get("source_system_exists", True)

    # Current values (may already be set from previous attempt)
    current_worker_type = state.get("worker_type") or defaults["worker_type"]
    current_workers = state.get("number_of_workers") or defaults["number_of_workers"]
    current_job_type = state.get("job_type") or defaults["job_type"]
    current_job_version = state.get("job_version") or defaults["job_version"]
    current_glue_version = state.get("glue_version") or defaults["glue_version"]
    current_ent_func = state.get("ent_func") or defaults["ent_func"]
    current_subgroup = state.get("subgroup") or defaults["subgroup"]
    current_scheduling = state.get("scheduling_mode") or defaults["scheduling_mode"]

    # Base fields — always shown
    base_fields = [
        {
            "name": "worker_type",
            "label": "Worker Type",
            "field_type": "select",
            "options": allowed_worker_types,
            "default": current_worker_type,
            "hint": "G.025X=0.25 DPU (lightweight), G.1X=1 DPU (standard), G.2X=2 DPU (heavy). saptcc uses G.2X.",
            "required": True,
        },
        {
            "name": "number_of_workers",
            "label": "Number of Workers",
            "field_type": "text",
            "placeholder": str(current_workers),
            "default": str(current_workers),
            "hint": "Range: 1–10. G.025X max 1 worker. saptcc uses 4.",
            "required": True,
        },
        {
            "name": "job_type",
            "label": "Job Type",
            "field_type": "select",
            "options": allowed_job_types,
            "default": current_job_type,
            "hint": "Use 'unified' for standard Kafka→Iceberg ingestion",
            "required": True,
        },
        {
            "name": "job_version",
            "label": "Job Version",
            "field_type": "text",
            "placeholder": current_job_version,
            "default": current_job_version,
            "hint": "Semver string, e.g. 0.3.0",
            "required": True,
        },
        {
            "name": "glue_version",
            "label": "Glue Version",
            "field_type": "text",
            "placeholder": current_glue_version,
            "default": current_glue_version,
            "hint": "AWS Glue version. Use 5.1 (real saptcc standard).",
            "required": True,
        },
        {
            "name": "scheduling_mode",
            "label": "Scheduling Mode",
            "field_type": "select",
            "options": ["manual", "scheduled"],
            "default": current_scheduling,
            "hint": "manual = triggered on demand, scheduled = cron",
            "required": True,
        },
        {
            "name": "trigger_schedule",
            "label": "Trigger Schedule (cron)",
            "field_type": "text",
            "placeholder": "cron(0 1 * * ? *)",
            "default": state.get("trigger_schedule") or "",
            "hint": "Only required if scheduling_mode = 'scheduled'. e.g. cron(0 5 * * ? *)",
            "required": False,
        },
    ]

    # ent_func and subgroup are FILE-LEVEL locals in locals.tf — only needed for NEW source systems
    new_system_note = ""
    if not source_system_exists:
        new_system_note = (
            "\n\n⚠️ **New source system detected.** "
            "`ent_func` and `subgroup` will be added as **file-level locals** "
            "at the top of the new `locals.tf` — not inside individual job blocks."
        )
        base_fields.extend([
            {
                "name": "ent_func",
                "label": "Enterprise Function (file-level)",
                "field_type": "select",
                "options": allowed_ent_funcs,
                "default": current_ent_func,
                "hint": "Goes at locals { ent_func = '...' } — applies to ALL jobs in this folder",
                "required": True,
            },
            {
                "name": "subgroup",
                "label": "Subgroup (file-level)",
                "field_type": "text",
                "placeholder": current_subgroup,
                "default": current_subgroup,
                "hint": "Goes at locals { subgroup = '...' } — applies to ALL jobs in this folder",
                "required": True,
            },
        ])

    message = {
        "role": "assistant",
        "content": (
            "Almost done! Configure the **worker settings** for this Glue job.\n\n"
            "The defaults below work for most cases. "
            "Override only if you have specific requirements.\n\n"
            "💡 **Tip:** `G.025X` supports max 1 worker. "
            "`G.2X` with 4 workers is the standard for saptcc-style jobs."
            + new_system_note
        ),
        "type": "assistant_message",
        "step": {
            "current": get_step_number(STEP_COLLECT_WORKERS),
            "total": TOTAL_STEPS,
            "label": "Worker Configuration"
        },
        "widget": {
            "type": "form",
            "fields": base_fields,
        },
    }

    return {
        **state,
        "current_step": STEP_COLLECT_WORKERS,
        "waiting_for_user": True,
        "messages": [message],
    }
