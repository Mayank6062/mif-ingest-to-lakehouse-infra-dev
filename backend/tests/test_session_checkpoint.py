"""
Tests for clear_session_checkpoint() in builder.py.

Covers STEP 20A bug fix (MemorySaver storage key format) and STEP 20 migration
to AsyncShallowRedisSaver.  clear_session_checkpoint() is now async and uses
graph.checkpointer.adelete_thread(session_id) — a public BaseCheckpointSaver
interface method compatible with both MemorySaver (tests) and AsyncShallowRedisSaver
(production).

Test matrix:
  T1 — storage key removed after clear
  T2 — writes keys removed after clear
  T3 — fresh astream after clear produces clean (non-duplicated) messages
  T4 — is_new_session flag is True after clear (websocket.py reconnect gate)
  T5 — clearing a non-existent session_id does not raise
  T6 — clearing one session does not affect other concurrent sessions

Architecture note — singleton injection
---------------------------------------
clear_session_checkpoint() calls get_compiled_graph() internally.  After STEP 20,
get_compiled_graph() raises RuntimeError if called before lifespan initializes the
singleton (no silent MemorySaver fallback).  Tests must inject their own minimal
compiled graph via _use_test_graph() — including T5 tests that clear non-existent
sessions.
"""

import asyncio
import contextlib
from typing import Annotated, List, TypedDict
import operator

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

import app.graph.builder as _builder_module
from app.graph.builder import clear_session_checkpoint


# ── Helpers ───────────────────────────────────────────────────────────────────

class _SimpleState(TypedDict):
    messages: Annotated[List[str], operator.add]
    step: str


def _build_test_graph(interrupt_before: list[str] | None = None):
    """
    Minimal two-node graph for testing checkpoint clear behaviour.
    node_a accumulates a message and advances to node_b.
    node_b accumulates a second message and ends.
    interrupt_before=['node_b'] pauses after node_a.
    """
    g = StateGraph(_SimpleState)

    def node_a(s: _SimpleState) -> dict:
        return {"step": "node_a", "messages": ["msg_from_a"]}

    def node_b(s: _SimpleState) -> dict:
        return {"step": "node_b", "messages": ["msg_from_b"]}

    g.add_node("node_a", node_a)
    g.add_node("node_b", node_b)
    g.set_entry_point("node_a")
    g.add_edge("node_a", "node_b")
    g.add_edge("node_b", END)

    cp = MemorySaver()
    interrupt = interrupt_before or []
    compiled = g.compile(checkpointer=cp, interrupt_before=interrupt)
    return compiled, cp


@contextlib.contextmanager
def _use_test_graph(interrupt_before: list[str] | None = None):
    """
    Context manager: inject a fresh test graph as the module singleton so that
    clear_session_checkpoint() operates on the test graph's checkpointer.
    Restores the original singleton on exit regardless of test outcome.
    """
    compiled, cp = _build_test_graph(interrupt_before=interrupt_before)
    original = _builder_module._compiled_graph
    _builder_module._compiled_graph = compiled
    try:
        yield compiled, cp
    finally:
        _builder_module._compiled_graph = original


def _run(coro):
    """Run a coroutine synchronously (works inside pytest without asyncio plugin)."""
    return asyncio.get_event_loop().run_until_complete(coro)


async def _stream_all(compiled, init_state: dict, config: dict) -> list[str]:
    """Run astream to completion, returning all collected messages."""
    msgs: list[str] = []
    async for chunk in compiled.astream(init_state, config, stream_mode="updates"):
        for node, update in chunk.items():
            if node != "__interrupt__" and isinstance(update, dict):
                msgs.extend(update.get("messages", []))
    return msgs


def _config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestT1StorageKeyRemovedAfterClear:
    """T1 — cp.storage no longer contains the session after clear_session_checkpoint."""

    def test_storage_key_absent_after_clear(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t1-session-abc"
            config = _config(sid)

            # Build a checkpoint
            _run(_stream_all(compiled, {"messages": [], "step": "start"}, config))

            # Precondition: storage entry exists
            # Under langgraph 1.x, the top-level key is the thread_id string
            assert sid in cp.storage, "Precondition: storage should contain session before clear"

            _run(clear_session_checkpoint(sid))

            # After clear, the key may be absent or its nested value must be empty.
            # defaultdict recreates the key on any __getitem__ access (e.g. via get_state),
            # so we check that get_state returns empty values rather than key absence alone.
            snap = compiled.get_state(config)
            assert snap.values == {}, (
                f"Expected empty snapshot after clear, got: {snap.values}"
            )

    def test_storage_values_empty_after_clear(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t1-session-values"
            config = _config(sid)

            _run(_stream_all(compiled, {"messages": [], "step": "start"}, config))
            assert compiled.get_state(config).values, "Precondition: should have values"

            _run(clear_session_checkpoint(sid))

            snap = compiled.get_state(config)
            assert not snap.values, f"Expected no values after clear, got: {snap.values}"
            assert snap.next == (), f"Expected no next nodes after clear, got: {snap.next}"


class TestT2WritesRemovedAfterClear:
    """T2 — cp.writes contains no entries for the session after clear_session_checkpoint."""

    def test_writes_absent_after_clear(self):
        with _use_test_graph(interrupt_before=["node_b"]) as (compiled, cp):
            sid = "t2-session-writes"
            config = _config(sid)

            # Run up to the interrupt — this generates writes entries
            _run(_stream_all(compiled, {"messages": [], "step": "start"}, config))

            # Precondition: writes should contain entries for this session
            writes_before = [k for k in cp.writes.keys() if k[0] == sid]
            assert writes_before, "Precondition: writes should contain entries before clear"

            _run(clear_session_checkpoint(sid))

            writes_after = [k for k in cp.writes.keys() if k[0] == sid]
            assert writes_after == [], (
                f"Expected no writes entries after clear, got: {writes_after}"
            )

    def test_writes_absent_after_full_run_and_clear(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t2-session-full"
            config = _config(sid)

            # Full run (no interrupt)
            _run(_stream_all(compiled, {"messages": [], "step": "start"}, config))

            _run(clear_session_checkpoint(sid))

            writes_after = [k for k in cp.writes.keys() if k[0] == sid]
            assert writes_after == [], (
                f"Expected no writes entries after clear of completed session, got: {writes_after}"
            )


class TestT3FreshStreamAfterClearProducesCleanMessages:
    """T3 — astream after clear produces only new messages, not accumulated old ones."""

    def test_messages_not_duplicated_after_restart(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t3-session-restart"
            config = _config(sid)

            # First run — accumulate messages
            first_msgs = _run(_stream_all(compiled, {"messages": [], "step": "s1"}, config))
            assert first_msgs, "Precondition: first run should produce messages"

            # Simulate restart: clear then re-stream fresh initial state
            _run(clear_session_checkpoint(sid))
            second_msgs = _run(_stream_all(compiled, {"messages": [], "step": "s2"}, config))

            # The second run should produce the same count as the first, not double
            assert len(second_msgs) == len(first_msgs), (
                f"Expected {len(first_msgs)} messages after restart, "
                f"got {len(second_msgs)}: {second_msgs}"
            )

    def test_messages_list_not_accumulated_across_restart(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t3-session-accum"
            config = _config(sid)

            # First run
            _run(_stream_all(compiled, {"messages": [], "step": "run1"}, config))
            snap1 = compiled.get_state(config)
            msgs_after_first = snap1.values.get("messages", [])

            # Clear and restart
            _run(clear_session_checkpoint(sid))
            _run(_stream_all(compiled, {"messages": [], "step": "run2"}, config))
            snap2 = compiled.get_state(config)
            msgs_after_second = snap2.values.get("messages", [])

            # After restart the accumulated messages list must not contain messages
            # from the previous session (i.e. no duplication)
            assert len(msgs_after_second) == len(msgs_after_first), (
                f"Messages accumulated across restart. "
                f"First run: {msgs_after_first}, Second run: {msgs_after_second}"
            )

    def test_step_field_reflects_new_session_after_clear(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t3-session-step"
            config = _config(sid)

            _run(_stream_all(compiled, {"messages": [], "step": "old_step"}, config))
            _run(clear_session_checkpoint(sid))
            _run(_stream_all(compiled, {"messages": [], "step": "new_step"}, config))

            snap = compiled.get_state(config)
            # node_b overwrites step to "node_b" — confirm it is not "old_step"
            assert snap.values.get("step") != "old_step", (
                f"Old step value persisted after restart: {snap.values.get('step')}"
            )


class TestT4IsNewSessionTrueAfterClear:
    """T4 — websocket.py's is_new_session check evaluates True after clear."""

    def test_is_new_session_true_after_clear(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t4-session-ws"
            config = _config(sid)

            _run(_stream_all(compiled, {"messages": [], "step": "init"}, config))

            snap_before = compiled.get_state(config)
            is_new_before = not (snap_before and snap_before.values)
            assert not is_new_before, "Precondition: is_new_session should be False before clear"

            _run(clear_session_checkpoint(sid))

            # Replicate exact logic from websocket.py
            snap_after = compiled.get_state(config)
            is_new_after = not (snap_after and snap_after.values)
            assert is_new_after, (
                f"Expected is_new_session=True after clear, "
                f"but snapshot.values={snap_after.values}"
            )

    def test_is_new_session_true_after_clear_with_interrupt(self):
        """Verify behaviour when graph was paused at interrupt_before point."""
        with _use_test_graph(interrupt_before=["node_b"]) as (compiled, cp):
            sid = "t4-session-interrupt"
            config = _config(sid)

            # Run up to interrupt — session is mid-workflow
            _run(_stream_all(compiled, {"messages": [], "step": "init"}, config))

            snap_mid = compiled.get_state(config)
            assert snap_mid.next == ("node_b",), "Precondition: should be paused at node_b"

            _run(clear_session_checkpoint(sid))

            snap_cleared = compiled.get_state(config)
            is_new = not (snap_cleared and snap_cleared.values)
            assert is_new, (
                f"Expected is_new_session=True after clearing mid-workflow session, "
                f"got snapshot.values={snap_cleared.values}, next={snap_cleared.next}"
            )


class TestT5ClearNonExistentSessionDoesNotRaise:
    """T5 — clear_session_checkpoint on an unknown session_id must not raise."""

    def test_clear_unknown_session_id(self):
        with _use_test_graph():
            _run(clear_session_checkpoint("session-that-never-existed-xyzzy"))

    def test_clear_empty_string_session_id(self):
        with _use_test_graph():
            _run(clear_session_checkpoint(""))

    def test_clear_called_twice_on_same_session(self):
        with _use_test_graph() as (compiled, cp):
            sid = "t5-double-clear"
            config = _config(sid)

            _run(_stream_all(compiled, {"messages": [], "step": "x"}, config))

            # First clear — functional
            _run(clear_session_checkpoint(sid))
            # Second clear — must not raise even though session is already gone
            _run(clear_session_checkpoint(sid))


class TestT6ClearDoesNotAffectOtherSessions:
    """T6 — clearing one session leaves all other sessions intact."""

    def test_other_session_unaffected_by_clear(self):
        with _use_test_graph() as (compiled, cp):
            sid_a = "t6-session-alpha"
            sid_b = "t6-session-beta"
            config_a = _config(sid_a)
            config_b = _config(sid_b)

            # Build state for both sessions
            _run(_stream_all(compiled, {"messages": [], "step": "a"}, config_a))
            _run(_stream_all(compiled, {"messages": [], "step": "b"}, config_b))

            snap_b_before = compiled.get_state(config_b)
            assert snap_b_before.values, "Precondition: session B should have values"

            # Clear only session A
            _run(clear_session_checkpoint(sid_a))

            # Session A must be cleared
            snap_a_after = compiled.get_state(config_a)
            assert not snap_a_after.values, (
                f"Expected session A to be cleared, got: {snap_a_after.values}"
            )

            # Session B must be untouched
            snap_b_after = compiled.get_state(config_b)
            assert snap_b_after.values == snap_b_before.values, (
                f"Session B was affected by clearing session A. "
                f"Before: {snap_b_before.values}, After: {snap_b_after.values}"
            )

    def test_writes_of_other_session_unaffected(self):
        with _use_test_graph(interrupt_before=["node_b"]) as (compiled, cp):
            sid_a = "t6-writes-alpha"
            sid_b = "t6-writes-beta"
            config_a = _config(sid_a)
            config_b = _config(sid_b)

            _run(_stream_all(compiled, {"messages": [], "step": "a"}, config_a))
            _run(_stream_all(compiled, {"messages": [], "step": "b"}, config_b))

            writes_b_before = [k for k in cp.writes.keys() if k[0] == sid_b]
            assert writes_b_before, "Precondition: session B should have write entries"

            _run(clear_session_checkpoint(sid_a))

            writes_a_after = [k for k in cp.writes.keys() if k[0] == sid_a]
            writes_b_after = [k for k in cp.writes.keys() if k[0] == sid_b]

            assert writes_a_after == [], "Session A writes should be cleared"
            assert len(writes_b_after) == len(writes_b_before), (
                f"Session B writes were affected. Before: {writes_b_before}, After: {writes_b_after}"
            )

    def test_many_concurrent_sessions_only_target_cleared(self):
        with _use_test_graph() as (compiled, cp):
            sessions = [f"t6-multi-{i}" for i in range(5)]
            configs = [_config(s) for s in sessions]

            for cfg in configs:
                _run(_stream_all(compiled, {"messages": [], "step": "x"}, cfg))

            target = sessions[2]
            _run(clear_session_checkpoint(target))

            # Target is gone
            assert not compiled.get_state(_config(target)).values

            # All others survive
            for sid, cfg in zip(sessions, configs):
                if sid == target:
                    continue
                snap = compiled.get_state(cfg)
                assert snap.values, f"Session {sid} was incorrectly cleared"
