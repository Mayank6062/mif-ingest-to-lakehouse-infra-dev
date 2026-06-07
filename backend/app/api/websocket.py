"""
WebSocket handler — real-time channel between frontend and backend.
Pattern: ws://{host}/ws/{session_id}?token={session_token}

Authentication:
  The session_token issued by POST /api/sessions MUST be supplied as the
  `token` query parameter.  The token is validated against the SessionRegistry
  BEFORE websocket.accept() is called.  Connections with a missing, wrong, or
  expired token are rejected with WebSocket close code 1008 (Policy Violation)
  and the handshake is never completed.

State is persisted by LangGraph's MemorySaver checkpointer (keyed by session_id).
This handler only deals with transport: validate → accept → stream → persist.

Incoming message format:
  { "type": "user_message", "content": "...", "widget_value": {...} }
  { "type": "approval", "content": "yes" }

Outgoing message format:
  { "type": "assistant_message", "content": "...", "step": {...}, "widget": {...} }
  { "type": "terraform_preview", "terraform_hcl": "...", ... }
  { "type": "pr_created", "pr_url": "...", ... }
  { "type": "typing" }
  { "type": "error", "content": "..." }
"""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.api.processor import process_first_message, process_user_message
from app.graph.builder import get_compiled_graph
from app.graph.state import get_step_number, STEP_LABELS, STEP_ORDER, TOTAL_STEPS

router = APIRouter()


def _thread_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(default=""),
):
    """
    Main WebSocket endpoint — authenticated, one connection per user session.

    Rejects with 1008 (Policy Violation) if the token is absent, wrong, or expired.
    The session must first be created via POST /api/sessions.
    """
    # ── Authentication gate — MUST happen before accept() ────────────────────
    from app.models.session import get_session_registry
    if not get_session_registry().validate_token(session_id, token):
        await websocket.close(code=1008)  # 1008 = Policy Violation
        return

    await websocket.accept()

    # Check if the graph already has a checkpoint for this session
    graph = get_compiled_graph()
    snapshot = graph.get_state(_thread_config(session_id))
    is_new_session = not (snapshot and snapshot.values)

    if is_new_session:
        # New session — run collect_topic_node, send initial widget
        opening_messages = await process_first_message(session_id)
        for msg in opening_messages:
            await websocket.send_json(msg)
    else:
        # Reconnecting — report the current step from checkpointed state
        values = snapshot.values
        current_step = values.get("current_step", "collect_topic")
        step_index = get_step_number(current_step)

        # Compute completed steps (all steps before current in STEP_ORDER)
        try:
            position = STEP_ORDER.index(current_step)
        except ValueError:
            position = 0
        completed_steps = list(STEP_ORDER[:position])

        # Derive validation_failed: validation ran and failed (not just initial False)
        validation_results = values.get("validation_results") or []
        validation_failed = (
            not values.get("validation_passed", False)
            and bool(validation_results)
        )

        await websocket.send_json({
            "type": "reconnected",
            "content": f"Welcome back! Resuming from step: **{current_step}**",
            "current_step": current_step,
            "step": {
                "current": step_index,
                "total": TOTAL_STEPS,
                "label": STEP_LABELS.get(current_step, current_step),
            },
            "completed_steps": completed_steps,
            "validation_failed": validation_failed,
            "validation_passed": values.get("validation_passed", False),
            "user_approved": values.get("user_approved"),
            "pr_url": values.get("pr_url"),
            "error_message": values.get("error_message"),
        })

    # ── Main message loop ─────────────────────────────────────────────────
    try:
        while True:
            raw = await websocket.receive_text()

            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError:
                incoming = {"type": "user_message", "content": raw}

            content      = incoming.get("content", "")
            widget_value = incoming.get("widget_value")

            # Send typing indicator
            await websocket.send_json({"type": "typing"})

            try:
                new_messages = await process_user_message(
                    session_id=session_id,
                    user_input=content,
                    widget_value=widget_value,
                )
            except Exception as exc:
                await websocket.send_json({
                    "type": "error",
                    "content": f"An error occurred: {str(exc)}",
                })
                continue

            await websocket.send_json({"type": "stop_typing"})
            for msg in new_messages:
                await websocket.send_json(msg)

    except WebSocketDisconnect:
        pass  # Client disconnected — checkpoint preserved for reconnection
