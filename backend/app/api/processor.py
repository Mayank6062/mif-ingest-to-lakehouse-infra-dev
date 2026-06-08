"""
Message processor — advances the workflow via LangGraph graph.astream().

Architecture:
  - State is persisted by the MemorySaver checkpointer inside the compiled graph.
  - interrupt_before declarations in builder.py pause execution at human steps.
  - On each user message, _map_user_input_to_state() converts widget values to
    the correct state fields, then graph.astream() resumes and runs forward
    through all auto-advance nodes until the next interrupt point.
  - No manual node dispatch, no _run_node(), no _apply_delta().
"""

import asyncio

from app.graph.state import (
    GlueJobState,
    STEP_COLLECT_TOPIC, STEP_DERIVE_VALUES,
    STEP_CONFIRM_DERIVED, STEP_COLLECT_SINK, STEP_COLLECT_WORKERS,
    STEP_RUN_VALIDATION, STEP_TERRAFORM_PREVIEW, STEP_APPROVAL,
    initial_state,
)
from app.graph.builder import get_compiled_graph, clear_session_checkpoint


# ── Thread config ─────────────────────────────────────────────────────────────

def _thread_config(session_id: str, *, action: str = "step") -> dict:
    """LangGraph thread config — ties graph execution to a session."""
    return {
        "configurable": {"thread_id": session_id},
        "metadata": {
            "session_id": session_id,
            "action": action,
        },
        "tags": ["glue-job-agent", action],
        "run_name": f"glue-job-{session_id[:8]}",
    }


def _get_current_step(session_id: str) -> str:
    """Read current_step from the graph's checkpointed state."""
    graph = get_compiled_graph()
    snapshot = graph.get_state(_thread_config(session_id))
    if snapshot and snapshot.values:
        return snapshot.values.get("current_step", STEP_COLLECT_TOPIC)
    return STEP_COLLECT_TOPIC


async def _get_current_step_async(session_id: str) -> str:
    """Async version: Read current_step from the graph's checkpointed state."""
    graph = get_compiled_graph()
    snapshot = await graph.aget_state(_thread_config(session_id))
    if snapshot and snapshot.values:
        return snapshot.values.get("current_step", STEP_COLLECT_TOPIC)
    return STEP_COLLECT_TOPIC


# ── Input mapping (replaces all _handle_*() functions) ───────────────────────

def _map_user_input_to_state(
    current_step: str,
    user_input: str,
    widget_value,
) -> dict:
    """
    Convert the user response to the state fields the graph needs on resume.
    current_step is the step that RAN last (set by the node before interrupt).
    """
    if current_step == STEP_COLLECT_TOPIC:
        topic = (widget_value or user_input or "").strip()
        return {"topic": topic, "raw_user_input": topic}

    if current_step == STEP_DERIVE_VALUES:
        form = widget_value if isinstance(widget_value, dict) else {}
        return {
            "job_key": form.get("job_key", ""),
            "kafka_secret_name": form.get("kafka_secret_name", ""),
        }

    if current_step == STEP_CONFIRM_DERIVED:
        answer = (widget_value or user_input or "").strip().lower()
        confirmed = any(
            kw in answer
            for kw in ["yes", "correct", "confirm", "continue", "ok", "proceed"]
        )
        return {"user_confirmed_derived": confirmed}

    if current_step == STEP_COLLECT_SINK:
        form = widget_value if isinstance(widget_value, dict) else {}
        return {
            "iceberg_database": form.get("iceberg_database", ""),
            "iceberg_warehouse": form.get("iceberg_warehouse", ""),
            "assume_role_arn":   form.get("assume_role_arn", ""),
        }

    if current_step == STEP_COLLECT_WORKERS:
        form = widget_value if isinstance(widget_value, dict) else {}
        from app.knowledge.loader import get_knowledge_base
        d = get_knowledge_base().defaults
        return {
            "worker_type":       form.get("worker_type",       d["worker_type"]),
            "number_of_workers": int(form.get("number_of_workers", d["number_of_workers"])),
            "job_type":          form.get("job_type",          d["job_type"]),
            "job_version":       form.get("job_version",       d["job_version"]),
            "glue_version":      form.get("glue_version",      d["glue_version"]),
            "ent_func":          form.get("ent_func",          d["ent_func"]),
            "subgroup":          form.get("subgroup",          d["subgroup"]),
            "scheduling_mode":   form.get("scheduling_mode",   d["scheduling_mode"]),
            "trigger_schedule":  form.get("trigger_schedule"),
        }

    if current_step in (STEP_TERRAFORM_PREVIEW, STEP_APPROVAL):
        answer = (widget_value or user_input or "").strip().lower()
        approved = any(
            kw in answer
            for kw in ["yes", "approve", "create", "submit", "ok", "confirm"]
        )
        return {"user_approved": approved}

    return {}


# ── Graph streaming helper ────────────────────────────────────────────────────

async def _stream_graph(state_update, thread_config: dict) -> list:
    """
    Resume graph with state_update, collect all new messages via astream.
    stream_mode=updates yields only each node delta — no slicing needed.
    """
    graph = get_compiled_graph()
    new_messages = []
    async for chunk in graph.astream(state_update, thread_config, stream_mode="updates"):
        for node_name, node_update in chunk.items():
            if node_name == "__interrupt__":
                continue
            if isinstance(node_update, dict):
                new_messages.extend(node_update.get("messages", []))
    return new_messages


# ── Public API ────────────────────────────────────────────────────────────────

async def process_first_message(session_id: str) -> list:
    """
    New session: run collect_topic_node, pause at interrupt_before DERIVE_VALUES.
    Returns the initial messages (topic input widget).
    """
    thread_config = _thread_config(session_id, action="new")
    init = initial_state(session_id)
    return await _stream_graph(init, thread_config)


async def process_user_message(session_id: str, user_input: str, widget_value=None) -> list:
    """
    Each user message: map input to state, resume graph, return new messages.
    """
    thread_config = _thread_config(session_id)

    user_msg = {
        "role": "user",
        "content": user_input,
        "type": "user_message",
    }

    # Global restart
    if user_input.strip().lower() in {"restart", "start over", "reset", "/restart"}:
        await clear_session_checkpoint(session_id)
        new_msgs = await process_first_message(session_id)
        return new_msgs

    # Inline field-edit from compact card
    if isinstance(widget_value, dict) and widget_value.get("_edit_type"):
        edit_type = widget_value.get("_edit_type")
        clean = {k: v for k, v in widget_value.items() if k != "_edit_type"}
        graph = get_compiled_graph()
        snapshot = await graph.aget_state(thread_config)
        cur = snapshot.values or {}

        if edit_type == "sink":
            state_update = {
                "iceberg_database": clean.get("iceberg_database", cur.get("iceberg_database", "")),
                "iceberg_warehouse": clean.get("iceberg_warehouse", cur.get("iceberg_warehouse", "")),
                "assume_role_arn":   clean.get("assume_role_arn",   cur.get("assume_role_arn", "")),
            }
        elif edit_type == "derived":
            state_update = {
                "job_key": clean.get("job_key", cur.get("job_key", "")),
                "kafka_secret_name": clean.get("kafka_secret_name", cur.get("kafka_secret_name", "")),
            }
        elif edit_type == "workers":
            # Route through the same mapping function as the normal workers step
            # to apply int() coercion on number_of_workers and knowledge-base defaults.
            # This prevents direct dict injection bypassing _map_user_input_to_state().
            state_update = _map_user_input_to_state(STEP_COLLECT_WORKERS, "", clean)
        else:
            return []

        thread_config = _thread_config(session_id, action="edit")
        await graph.aupdate_state(thread_config, state_update, STEP_COLLECT_WORKERS)
        new_msgs = await _stream_graph(None, thread_config)
        return new_msgs

    # Normal step: update checkpoint then resume from interrupt
    current_step = await _get_current_step_async(session_id)
    state_update = _map_user_input_to_state(current_step, user_input, widget_value)

    # Special case: user rejected confirm_derived — restart from Step 1 immediately
    # (the conditional edge _route_after_confirm_derived is evaluated BEFORE the
    # interrupt fires, so we cannot rely on the routing to handle rejection;
    # we must clear the checkpoint and start fresh here instead)
    if current_step == STEP_CONFIRM_DERIVED and state_update.get("user_confirmed_derived") is False:
        await clear_session_checkpoint(session_id)
        new_msgs = await process_first_message(session_id)
        return new_msgs

    graph = get_compiled_graph()
    await graph.aupdate_state(thread_config, state_update)
    new_msgs = await _stream_graph(None, thread_config)
    return new_msgs
