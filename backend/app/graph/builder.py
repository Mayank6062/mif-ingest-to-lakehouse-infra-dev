"""
Graph builder — wires all nodes into a compiled LangGraph StateGraph.

Interrupt points (human-in-the-loop):
  DERIVE_VALUES    — pause AFTER collect_topic presents the input widget
  COLLECT_SINK     — pause AFTER confirm_derived presents the confirmation widget
  COLLECT_WORKERS  — pause AFTER collect_sink presents the sink form
  RUN_VALIDATION   — pause AFTER collect_workers presents the worker form
  APPROVAL         — pause AFTER terraform_preview presents the HCL + approval widget

On resume, processor.py calls graph.astream(state_update, thread_config)
with the fields the user just provided. The graph applies the update,
runs forward through all auto-advance nodes, and stops at the next interrupt.
"""

from langgraph.graph import StateGraph, END

from app.graph.state import (
    GlueJobState,
    STEP_COLLECT_TOPIC,
    STEP_DERIVE_VALUES,
    STEP_CHECK_KAFKA_TOPIC,
    STEP_CHECK_SOURCE,
    STEP_CONFIRM_DERIVED,
    STEP_COLLECT_SINK,
    STEP_COLLECT_WORKERS,
    STEP_RUN_VALIDATION,
    STEP_SHOW_SUMMARY,
    STEP_GENERATE_TERRAFORM,
    STEP_TERRAFORM_PREVIEW,
    STEP_APPROVAL,
    STEP_CREATE_PR,
)
from app.graph.nodes.collect_topic import collect_topic_node
from app.graph.nodes.derive_values import derive_values_node
from app.graph.nodes.check_kafka_topic import check_kafka_topic_node
from app.graph.nodes.check_source_system import check_source_system_node
from app.graph.nodes.confirm_derived import confirm_derived_node
from app.graph.nodes.collect_sink import collect_sink_node
from app.graph.nodes.collect_workers import collect_workers_node
from app.graph.nodes.run_validation import run_validation_node
from app.graph.nodes.show_summary import show_summary_node
from app.graph.nodes.generate_terraform import generate_terraform_node
from app.graph.nodes.terraform_preview import terraform_preview_node
from app.graph.nodes.create_pr import create_pr_node
from app.services.audit_log import log_event
from app.config import get_settings


# ── Routing functions (conditional edges) ────────────────────────────────────

def _route_after_derive(state: GlueJobState) -> str:
    """After derive_values: go to check_source or restart if derivation failed."""
    if state.get("current_step") == STEP_COLLECT_TOPIC:
        return STEP_COLLECT_TOPIC
    return STEP_CHECK_SOURCE


def _route_after_kafka_check(state: GlueJobState) -> str:
    """After check_kafka_topic: back to collect_topic on Rule 1 (topic missing), else derive_values."""
    if state.get("kafka_topic_missing"):
        return STEP_COLLECT_TOPIC
    return STEP_DERIVE_VALUES


def _route_after_confirm_derived(state: GlueJobState) -> str:
    """After confirm_derived: proceed to sink form, or restart if user rejected."""
    if state.get("user_confirmed_derived") is False:
        return STEP_COLLECT_TOPIC   # User said "no" — restart from topic entry
    return STEP_COLLECT_SINK


def _route_after_validation(state: GlueJobState) -> str:
    """After run_validation: go to summary if passed, back to sink form if failed."""
    if state.get("validation_passed", False):
        return STEP_SHOW_SUMMARY
    return STEP_COLLECT_SINK


def _route_after_approval(state: GlueJobState) -> str:
    """After approval_router: create PR if approved, end gracefully if rejected."""
    if state.get("user_approved"):
        return STEP_CREATE_PR
    return END


# ── Approval router node (inline — not a domain node) ────────────────────────

def _approval_router_node(state: GlueJobState) -> GlueJobState:
    """
    Runs after terraform_preview, after the user's approval/rejection is loaded.
    - Approved: no-op (graph routes to create_pr via conditional edge).
    - Rejected: emits a cancellation message and routes to END.
    """
    if not state.get("user_approved"):
        log_event("approval_rejected", "user", state)
        cancel_msg = {
            "role": "assistant",
            "content": (
                "✋ **Pull Request creation cancelled.**\n\n"
                "No changes were made to the repository.\n"
                "Type **'restart'** if you'd like to start a new Glue job."
            ),
            "type": "assistant_message",
        }
        return {
            "current_step": STEP_APPROVAL,
            "user_approved": False,
            "waiting_for_user": False,
            "messages": [cancel_msg],
        }
    # Approved — pass through with no state change (create_pr node handles the work)
    return {}


# ── Graph construction ────────────────────────────────────────────────────────

def build_graph(checkpointer):
    """
    Build and compile the LangGraph StateGraph with the provided checkpointer
    and interrupt_before declarations for all human-in-the-loop steps.
    """
    graph = StateGraph(GlueJobState)

    # ── Register nodes ─────────────────────────────────────────────────────
    graph.add_node(STEP_COLLECT_TOPIC,       collect_topic_node)
    graph.add_node(STEP_DERIVE_VALUES,       derive_values_node)
    graph.add_node(STEP_CHECK_KAFKA_TOPIC,   check_kafka_topic_node)
    graph.add_node(STEP_CHECK_SOURCE,        check_source_system_node)
    graph.add_node(STEP_CONFIRM_DERIVED,    confirm_derived_node)
    graph.add_node(STEP_COLLECT_SINK,       collect_sink_node)
    graph.add_node(STEP_COLLECT_WORKERS,    collect_workers_node)
    graph.add_node(STEP_RUN_VALIDATION,     run_validation_node)
    graph.add_node(STEP_SHOW_SUMMARY,       show_summary_node)
    graph.add_node(STEP_GENERATE_TERRAFORM, generate_terraform_node)
    graph.add_node(STEP_TERRAFORM_PREVIEW,  terraform_preview_node)
    graph.add_node(STEP_APPROVAL,           _approval_router_node)
    graph.add_node(STEP_CREATE_PR,          create_pr_node)

    # ── Entry point ────────────────────────────────────────────────────────
    graph.set_entry_point(STEP_COLLECT_TOPIC)

    # ── Edges ──────────────────────────────────────────────────────────────

    # collect_topic → check_kafka_topic (moved to step 2 for early validation)
    # (interrupt_before COLLECT_TOPIC pauses here for user to enter topic)
    graph.add_edge(STEP_COLLECT_TOPIC, STEP_CHECK_KAFKA_TOPIC)

    # check_kafka_topic → derive_values  OR  back to collect_topic if topic invalid
    graph.add_conditional_edges(
        STEP_CHECK_KAFKA_TOPIC,
        _route_after_kafka_check,
        {
            STEP_COLLECT_TOPIC: STEP_COLLECT_TOPIC,
            STEP_DERIVE_VALUES: STEP_DERIVE_VALUES,
        },
    )

    # derive_values → check_source  OR  back to collect_topic if derivation fails
    graph.add_conditional_edges(
        STEP_DERIVE_VALUES,
        _route_after_derive,
        {
            STEP_COLLECT_TOPIC: STEP_COLLECT_TOPIC,
            STEP_CHECK_SOURCE:  STEP_CHECK_SOURCE,
        },
    )

    # check_source → confirm_derived (auto)
    graph.add_edge(STEP_CHECK_SOURCE, STEP_CONFIRM_DERIVED)

    # confirm_derived → collect_sink  OR  back to collect_topic if user said "no"
    # (interrupt_before COLLECT_SINK pauses here for user to confirm/reject)
    graph.add_conditional_edges(
        STEP_CONFIRM_DERIVED,
        _route_after_confirm_derived,
        {
            STEP_COLLECT_SINK:   STEP_COLLECT_SINK,
            STEP_COLLECT_TOPIC:  STEP_COLLECT_TOPIC,
        },
    )

    # collect_sink → collect_workers
    # (interrupt_before COLLECT_WORKERS pauses here for user to submit sink form)
    graph.add_edge(STEP_COLLECT_SINK, STEP_COLLECT_WORKERS)

    # collect_workers → run_validation
    # (interrupt_before RUN_VALIDATION pauses here for user to submit worker form)
    graph.add_edge(STEP_COLLECT_WORKERS, STEP_RUN_VALIDATION)

    # run_validation → show_summary  OR  back to collect_sink if validation failed
    graph.add_conditional_edges(
        STEP_RUN_VALIDATION,
        _route_after_validation,
        {
            STEP_SHOW_SUMMARY: STEP_SHOW_SUMMARY,
            STEP_COLLECT_SINK: STEP_COLLECT_SINK,
        },
    )

    # Auto-advance chain: summary → generate → preview
    graph.add_edge(STEP_SHOW_SUMMARY,       STEP_GENERATE_TERRAFORM)
    graph.add_edge(STEP_GENERATE_TERRAFORM, STEP_TERRAFORM_PREVIEW)

    # terraform_preview → approval router
    # (interrupt_before APPROVAL pauses here for user to approve/reject)
    graph.add_edge(STEP_TERRAFORM_PREVIEW, STEP_APPROVAL)

    # approval router → create_pr  OR  END (if rejected)
    graph.add_conditional_edges(
        STEP_APPROVAL,
        _route_after_approval,
        {
            STEP_CREATE_PR: STEP_CREATE_PR,
            END:            END,
        },
    )

    graph.add_edge(STEP_CREATE_PR, END)

    # ── Compile with provided checkpointer + interrupt_before ─────────────
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=[
            STEP_CHECK_KAFKA_TOPIC,  # pause after collect_topic (user enters topic, then Kafka check)
            STEP_DERIVE_VALUES,      # pause after kafka_check (for Rules 2/3 approval, before auto-derive)
            STEP_CHECK_SOURCE,       # pause after derive_values (source system decision)
            STEP_COLLECT_SINK,       # pause after confirm_derived (confirmation)
            STEP_COLLECT_WORKERS,    # pause after collect_sink (sink form)
            STEP_RUN_VALIDATION,     # pause after collect_workers (worker form)
            STEP_APPROVAL,           # pause after terraform_preview (HCL + approval)
        ],
    )


# ── Singleton compiled graph (initialized by lifespan in main.py) ─────────────

_compiled_graph = None


def get_compiled_graph():
    if _compiled_graph is None:
        raise RuntimeError(
            "Graph not initialized. Lifespan startup must run first."
        )
    return _compiled_graph


def initialize_graph(checkpointer) -> None:
    """Set the compiled graph singleton. Called once from FastAPI lifespan."""
    global _compiled_graph
    _compiled_graph = build_graph(checkpointer)


async def clear_session_checkpoint(session_id: str) -> None:
    """Clear the LangGraph checkpoint for a session (used on restart/delete)."""
    graph = get_compiled_graph()
    await graph.checkpointer.adelete_thread(session_id)
