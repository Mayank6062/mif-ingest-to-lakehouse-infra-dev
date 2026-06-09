"""
LangGraph state definition for the Glue Job Creation workflow.
This state is the single source of truth for a user session.
Annotated fields accumulate (messages list), non-annotated fields overwrite.
"""

from __future__ import annotations
from typing import TypedDict, Optional, List, Annotated
import operator
from app.models.chat import ChatMessage, ValidationResult


# ─── Workflow Step Constants ─────────────────────────────────────────────────

STEP_COLLECT_TOPIC = "collect_topic"
STEP_DERIVE_VALUES = "derive_values"
STEP_CHECK_KAFKA_TOPIC = "check_kafka_topic"
STEP_CHECK_SOURCE = "check_source_system"
STEP_CONFIRM_DERIVED = "confirm_derived"
STEP_COLLECT_SINK = "collect_sink"
STEP_COLLECT_WORKERS = "collect_workers"
STEP_RUN_VALIDATION = "run_validation"
STEP_SHOW_SUMMARY = "show_summary"
STEP_GENERATE_TERRAFORM = "generate_terraform"
STEP_TERRAFORM_PREVIEW = "terraform_preview"
STEP_APPROVAL = "approval"
STEP_VALIDATE_TERRAFORM = "validate_terraform"
STEP_CREATE_PR = "create_pr"
STEP_PR_SUCCESS = "pr_success"
STEP_ERROR = "error"

STEP_ORDER = [
    STEP_COLLECT_TOPIC,
    STEP_CHECK_KAFKA_TOPIC,
    STEP_DERIVE_VALUES,
    STEP_CHECK_SOURCE,
    STEP_CONFIRM_DERIVED,
    STEP_COLLECT_SINK,
    STEP_COLLECT_WORKERS,
    STEP_RUN_VALIDATION,
    STEP_SHOW_SUMMARY,
    STEP_GENERATE_TERRAFORM,
    STEP_TERRAFORM_PREVIEW,
    STEP_APPROVAL,
    STEP_VALIDATE_TERRAFORM,
    STEP_CREATE_PR,
    STEP_PR_SUCCESS,
]

STEP_LABELS = {
    STEP_COLLECT_TOPIC: "Enter Kafka Topic",
    STEP_DERIVE_VALUES: "Deriving Values",
    STEP_CHECK_KAFKA_TOPIC: "Checking Kafka Topic",
    STEP_CHECK_SOURCE: "Checking Source System",
    STEP_CONFIRM_DERIVED: "Confirm Derived Values",
    STEP_COLLECT_SINK: "Sink Configuration",
    STEP_COLLECT_WORKERS: "Worker Configuration",
    STEP_RUN_VALIDATION: "Running Validations",
    STEP_SHOW_SUMMARY: "Review Summary",
    STEP_GENERATE_TERRAFORM: "Generating Terraform",
    STEP_TERRAFORM_PREVIEW: "Terraform Preview",
    STEP_APPROVAL: "Awaiting Approval",
    STEP_VALIDATE_TERRAFORM: "Validating Terraform",
    STEP_CREATE_PR: "Creating Pull Request",
    STEP_PR_SUCCESS: "Pull Request Created",
}

TOTAL_STEPS = len(STEP_ORDER)

# Steps that require user input (the graph waits after these)
USER_INPUT_STEPS = {
    STEP_COLLECT_TOPIC,
    STEP_CONFIRM_DERIVED,
    STEP_COLLECT_SINK,
    STEP_COLLECT_WORKERS,
    STEP_APPROVAL,
}


# ─── State TypedDict ──────────────────────────────────────────────────────────

class GlueJobState(TypedDict, total=False):
    """
    Complete state for one Glue Job creation session.
    Flows through every LangGraph node.
    """

    # Session identity
    session_id: str
    current_step: str
    waiting_for_user: bool
    error_message: Optional[str]
    retry_count: int

    # Message history (accumulated — never overwritten)
    messages: Annotated[List[dict], operator.add]

    # ── STEP 1: Topic ─────────────────────────────────────────────────────
    topic: Optional[str]
    raw_user_input: Optional[str]   # original uncleaned input

    # ── STEP 2b: Kafka + Schema Registry check ──────────────────────────────
    kafka_topic_exists: Optional[bool]           # True if topic found in Kafka broker
    kafka_topic_missing: Optional[bool]          # True when Rule 1 fires (drives routing)
    schema_registry_available: Optional[bool]    # True if SR responded successfully
    schema_count: Optional[int]                  # Count of matching subjects (prefix match)
    schema_exists: Optional[bool]                # True when schema_count > 0
    schema_check_needs_approval: Optional[bool]  # True for Rule 2 and Rule 3
    user_accepted_kafka_check: Optional[bool]    # User response to Rules 2/3 approval

    # ── STEP 2: Derived values ────────────────────────────────────────────
    environment: Optional[str]       # dev | snd | prod
    source_system: Optional[str]     # saptcc | wahoo | sfsc ...
    schema_grain: Optional[str]      # multi-1 | cdhdr | bseg ...
    job_key: Optional[str]           # kafka-to-iceberg-batch-saptcc-multi-1
    kafka_secret_name: Optional[str] # minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds

    # ── STEP 3: Source system check ───────────────────────────────────────
    source_system_exists: Optional[bool]
    source_system_pattern: Optional[str]  # local_module | external_module | new
    source_system_display_name: Optional[str]
    knowledge_base_source_system_exists: Optional[bool]
    github_source_system_exists: Optional[bool]
    source_system_decision_source: Optional[str]
    source_system_locals_path: Optional[str]

    # ── STEP 4: Sink configuration ────────────────────────────────────────
    iceberg_database: Optional[str]
    iceberg_warehouse: Optional[str]
    checkpoint_dir: Optional[str]
    assume_role_arn: Optional[str]

    # ── STEP 5: Worker / job configuration ───────────────────────────────
    worker_type: str          # default: G.1X
    number_of_workers: int    # default: 2
    job_type: str             # default: unified
    job_version: str          # default: 0.3.0
    glue_version: str         # default: 5.1 (confirmed saptcc standard)
    ent_func: str             # default: AGTR
    subgroup: str             # default: APAC
    scheduling_mode: str      # manual | scheduled
    trigger_schedule: Optional[str]  # cron(0 1 * * ? *)

    # ── STEP 6: Validation results ────────────────────────────────────────
    validation_results: List[dict]   # List of ValidationResult dicts
    validation_passed: bool

    # ── STEP 8: Generated Terraform ──────────────────────────────────────
    terraform_hcl: Optional[str]          # job entry HCL (the block inside glue_jobs)
    locals_tf_full: Optional[str]         # NEW systems: full locals.tf content; existing: None
    glue_tf_content: Optional[str]        # glue.tf content (always generated, shown for reference)
    files_to_modify: List[str]
    pr_checklist: List[str]
    new_source_checklist: Optional[List[str]]
    # ── STEP 4b: Confirmation of derived values ─────────────────────────────
    # None = not yet answered, True = confirmed, False = rejected (restart)
    user_confirmed_derived: Optional[bool]
    # ── STEP 10: User approval ────────────────────────────────────────────
    user_approved: Optional[bool]

    # ── STEP 11: Terraform Validation ─────────────────────────────────────
    terraform_validation_status: Optional[str]   # pending | passed | failed
    terraform_validation_logs: Optional[str]     # stdout from all commands
    terraform_validation_errors: Optional[str]   # stderr from failed commands

    # ── STEP 12: Pull Request ─────────────────────────────────────────────
    pr_url: Optional[str]
    branch_name: Optional[str]
    pr_number: Optional[int]


def get_step_number(step: str) -> int:
    """Returns the 1-based step number for the given step name."""
    try:
        return STEP_ORDER.index(step) + 1
    except ValueError:
        return 0


def initial_state(session_id: str) -> GlueJobState:
    """Create a fresh initial state for a new session."""
    from app.knowledge.loader import get_knowledge_base
    kb = get_knowledge_base()
    defaults = kb.defaults

    return GlueJobState(
        session_id=session_id,
        current_step=STEP_COLLECT_TOPIC,
        waiting_for_user=True,
        error_message=None,
        retry_count=0,
        messages=[],
        # Topic
        topic=None,
        raw_user_input=None,
        # Derived
        environment=None,
        source_system=None,
        schema_grain=None,
        job_key=None,
        kafka_secret_name=None,
        # Source system check
        source_system_exists=None,
        source_system_pattern=None,
        source_system_display_name=None,
        knowledge_base_source_system_exists=None,
        github_source_system_exists=None,
        source_system_decision_source=None,
        source_system_locals_path=None,
        # Sink
        iceberg_database=None,
        iceberg_warehouse=None,
        # checkpoint_dir is FIXED: "s3://minerva-${local.env}-glue-checkpoints/checkpoints/unified/"
        # It is NOT user-provided — auto-emitted in HCL template as Terraform interpolation
        assume_role_arn=None,
        # Worker / job config (prefilled with defaults)
        worker_type=defaults["worker_type"],
        number_of_workers=defaults["number_of_workers"],
        job_type=defaults["job_type"],
        job_version=defaults["job_version"],
        glue_version="5.1",    # Real default from saptcc — not 5.0
        ent_func=defaults["ent_func"],
        subgroup=defaults["subgroup"],
        scheduling_mode=defaults["scheduling_mode"],
        trigger_schedule=None,
        # Validation
        validation_results=[],
        validation_passed=False,
        # Terraform
        terraform_hcl=None,
        files_to_modify=[],
        pr_checklist=[],
        new_source_checklist=None,
        # Confirmation
        user_confirmed_derived=None,
        # Approval
        user_approved=None,
        # Terraform validation
        terraform_validation_status=None,
        terraform_validation_logs=None,
        terraform_validation_errors=None,
        # PR
        pr_url=None,
        branch_name=None,
        pr_number=None,
    )
