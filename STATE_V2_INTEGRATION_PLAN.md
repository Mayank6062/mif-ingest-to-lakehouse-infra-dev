# STATE V2 Integration Plan

Date: 2026-06-12

Goal
----
Integrate State V2 into the existing LangGraph workflow so each user session has a single Draft Workspace for file edits. Preserve existing behavior (no breaking changes). Use SessionPersistenceService, DraftWorkspaceService, SnapshotEngine, and DiffEngine to support draft storage, snapshots, diffs, and rollback.

Constraints / Non-goals
- Do NOT change business flow or LangGraph node sequencing.
- No breaking changes for existing API/graph consumers.
- Design-only: no code changes in this document.

Overview — current components
-----------------------------
- LangGraph StateGraph (compiled in `app.graph.builder`)
- Checkpointer (graph-level): persists `GlueJobState` snapshots/threads
- `app.graph.state.GlueJobState`: authoritative in-memory state for a session
- `app.api.processor`: maps user input → state updates → graph.astream()
- `SessionPersistenceService` (existing): stores session metadata, TTLs
- `DraftWorkspaceService` (existing): create/apply edits to per-session draft workspaces
- `SnapshotEngine` (existing): capture draft workspace snapshots (for discard/restore)
- `DiffEngine` (existing): generate diffs of file changes

Files to inspect / touch (design-time)
- backend/app/graph/state.py
- backend/app/graph/builder.py
- backend/app/api/processor.py
- backend/app/graph/nodes/generate_terraform.py (and nodes that produce files)
- backend/app/graph/nodes/create_pr.py
- backend/app/services/draft_workspace_service.py
- backend/app/services/snapshot_engine.py
- backend/app/services/diff_engine.py
- backend/app/services/session_persistence.py
- backend/app/main.py (lifespan init)

Current authoritative state
---------------------------
- `GlueJobState` (typed dict) is the authoritative session state for the LangGraph execution. It contains all workflow fields and `messages` (accumulated). This is the "single source of truth" for workflow decisions.

Message lifecycle
-----------------
1. User submits input (chat or widget). `processor.process_user_message()` maps input to a partial state update.
2. `graph.aupdate_state(thread_config, state_update)` persists the delta via LangGraph checkpointer.
3. `graph.astream(...)` executes nodes producing node deltas (including `messages` to present back to UI). `processor._stream_graph()` collects messages and returns them to the client.
4. Messages are also stored on checkpointed state under `messages` so later restarts may re-surface them.

Session lifecycle
-----------------
- Create: client triggers `process_first_message(session_id)` → new `initial_state(session_id)` is used. Currently no explicit draft workspace created by default.
- Ongoing: each user reply updates the graph checkpoint; the graph and checkpointer keep the session state.
- Terminate / restart: Graph checkpoint may be cleared by `clear_session_checkpoint(session_id)` or expire; session metadata kept in SessionPersistenceService optionally.

Checkpoint lifecycle
--------------------
- LangGraph checkpointer persists per-session thread snapshots, including `values` (state values) and potentially a `messages` list.
- `clear_session_checkpoint(session_id)` removes the LangGraph thread state.

Design goals for State V2 integration
------------------------------------
- Introduce State V2 to augment the session state with Draft Workspace metadata and minimal routing info, while preserving `GlueJobState` semantics.
- Ensure one session → one Draft Workspace.
- All file edits produced by nodes (generate_terraform, preview, create_pr steps) are stored in the Draft Workspace instead of writing to the repo or ephemeral variables.
- SnapshotEngine used to implement "discard last change" (capture per-change snapshot and enable restore to last snapshot).
- DiffEngine records diffs for each file edit so the UI can show change summaries and audit log can persist diffs.
- Session history (messages + validation results + drafts) restored after restart by rehydrating graph state + draft workspace metadata.

High-level architecture (mermaid)
---------------------------------

```mermaid
flowchart LR
  subgraph UI
    U[User Client]
  end

  subgraph API
    P[processor.py]
  end

  subgraph LangGraph
    G[Compiled StateGraph]
    CP[Checkpointer]
  end

  subgraph Services
    SESS[SessionPersistenceService]
    DRAFT[DraftWorkspaceService]
    SNAP[SnapshotEngine]
    DIFF[DiffEngine]
    KB[KnowledgeBaseLoader]
    AUDIT[AuditLog]
  end

  U -->|message / widget| P
  P -->|map input| G
  G -->|state snapshots| CP
  G -->|file edits (delta)| DRAFT
  DRAFT --> DIFF
  DRAFT --> SNAP
  DRAFT --> SESS
  DIFF --> AUDIT
  SNAP --> SESS
  P --> SESS
  SESS -->|load meta| P
  P -->|create draft| DRAFT
```

Migration sequence (high-level)
------------------------------
1. Initialize integration flags & services (no runtime change):
   - Ensure `DraftWorkspaceService`, `SnapshotEngine`, `DiffEngine`, and `SessionPersistenceService` are available at app startup (main.py lifespan).
   - Add config entry: `ENABLE_STATE_V2 = True/False` (feature flag) to allow gradual rollout.

2. Extend `GlueJobState` (State V2 additions) **backward compatible**:
   - Add optional fields to `GlueJobState` (state.py):
     - `draft_workspace_id: Optional[str]`  # link to Draft Workspace
     - `draft_files: Optional[dict]`  # optional lightweight cache of filenames → metadata
     - `last_snapshot_id: Optional[str]`
     - `draft_change_history: Optional[list]`  # list of change metadata entries (diff ids)
   - Keep fields optional to ensure older checkpoints still load.

3. Session creation hook (minimal change to `processor.process_first_message`):
   - When a new session is created and feature flag enabled:
     - Call `DraftWorkspaceService.create(session_id)` → returns `draft_workspace_id`.
     - Attach `draft_workspace_id` to initial state before first graph run: `initial_state(session_id)['draft_workspace_id'] = id`.
     - Persist this as part of the first checkpoint via `graph.astream`.
   - Also register session metadata in `SessionPersistenceService` (session_id → draft_workspace_id, TTLs).

4. Per-file edit flow (nodes that create files):
   - Identify nodes that produce file content: `generate_terraform_node`, `terraform_preview_node` (renders HCL), plus any nodes that set `locals_tf_full` or `files_to_modify`.
   - Instead of storing full file content solely in state, have nodes emit a *file-edit delta* describing: `{path, content, author, timestamp, change_id}`.
   - Processor / Graph runtime should route these deltas to `DraftWorkspaceService.apply_edit(draft_id, path, content)`.
   - When apply_edit returns, call `DiffEngine.record(diff_metadata)` to capture delta; append change metadata to state field `draft_change_history` and to SessionPersistence.
   - Also call `SnapshotEngine.capture(draft_id, change_id)` to create snapshot point used for "discard last change".

5. "Discard last change" behavior
   - When user triggers discard last change (via UI action):
     - Use `SnapshotEngine.restore_to_snapshot(draft_id, last_snapshot_id)` to revert files in Draft Workspace to previous snapshot.
     - Optionally update `draft_change_history` and `last_snapshot_id` in the LangGraph checkpoint (use `graph.aupdate_state`).
     - Emit messages to user confirming the discard.

6. Restore on restart / resume
   - On process startup, `initialize_graph()` reads persisted checkpointer and compiles graph.
   - When processing a `process_first_message` or any resumed session, `processor` should consult `SessionPersistenceService` for draft workspace metadata for that session id.
   - If `draft_workspace_id` is present, rehydrate minimal draft metadata into the state (optionally not the full file contents to avoid checkpoint bloat). The graph will continue using persisted state + draft id to read current draft content from DraftWorkspaceService on-demand.

7. Read path for UI views
   - For previewing file contents in UI, call `DraftWorkspaceService.get_file(draft_id, path)` on-demand instead of reading from checkpointed state.

Files to modify (design-only)
-----------------------------
- `backend/app/graph/state.py`
  - Add optional V2 fields: `draft_workspace_id`, `draft_change_history`, `last_snapshot_id`, `draft_files` (metadata only)
- `backend/app/api/processor.py`
  - On `process_first_message` (new session), create draft workspace and embed `draft_workspace_id` into initial state.
  - On `process_user_message` when inline edits or nodes produce file edits, forward deltas to `DraftWorkspaceService` and record diffs/snapshots.
  - Implement a small adapter to synthesize approval/preview messages referencing Draft Workspace content via `DraftWorkspaceService.get_file`.
- `backend/app/graph/builder.py`
  - Ensure compiled graph checkpointer continues to persist the extended state; no change to graph logic required.
  - Optionally, include a `checkpointer` that can store small `draft_*` metadata and avoid large binary blobs in checkpoints.
- `backend/app/graph/nodes/generate_terraform.py`, `terraform_preview.py`, `create_pr.py`
  - Change node outputs to publish file-edit deltas (path + content + metadata) into node update rather than embedding big content into the core state.
  - Node logic should *not* write to repo; the create_pr node will still call GitHub service to open PR but based on Draft Workspace content.
- `backend/app/services/draft_workspace_service.py`
  - Ensure it supports: create(session_id), apply_edit(draft_id, path, content, meta), get_file(draft_id, path), list_files(draft_id), delete_snapshot(draft_id, snapshot_id), list_snapshots(draft_id).
- `backend/app/services/snapshot_engine.py` and `diff_engine.py`
  - Ensure APIs support capture(draft_id, change_id), restore(draft_id, snapshot_id), generate diff between snapshots and current draft, and return metadata that can be stored in state.
- `backend/app/services/session_persistence.py`
  - Store mapping `session_id → draft_workspace_id` and minimal draft metadata; used for session restore after restart.
- `backend/app/main.py` (lifespan)
  - Initialize DraftWorkspaceService, SnapshotEngine, DiffEngine, SessionPersistenceService and optionally a lightweight DraftCache.

Migration sequence (detailed steps)
----------------------------------
Phase 0 — Prep (no runtime switch)
- Add feature flag `ENABLE_STATE_V2` (default false). Wire services but do not change behavior.
- Add optional fields to `GlueJobState` (state.py) — no semantic change.
- Add non-invasive adapters in `DraftWorkspaceService` to operate in no-op mode if flag is false.

Phase 1 — Create Draft per session (read-only safe)
- Enable feature flag in staging.
- On new session creation, create draft (DraftWorkspaceService.create) and attach `draft_workspace_id` to initial state.
- No nodes yet write to draft; nodes continue to populate `terraform_hcl` etc. The draft is empty but linked.

Phase 2 — Route file edits to Draft Workspace (selective)
- Modify nodes that create HCL artifacts to emit file-edit deltas and have processor route deltas to DraftWorkspaceService.apply_edit.
- Continue to also keep `terraform_hcl` in state until UI changes fully rely on DraftWorkspaceService for reads.
- Record diffs and snapshots per change.

Phase 3 — Switch UI reads to DraftWorkspaceService
- Update preview/render endpoints to fetch file contents from DraftWorkspaceService instead of checkpointed `terraform_hcl` fields.
- Remove large `terraform_hcl` payloads from the checkpoint to reduce state size (optional, behind feature flag).

Phase 4 — Decommission in-state file content
- Once UI and nodes read/write via DraftWorkspaceService reliably, stop storing full file content in `GlueJobState` and keep only metadata and change history.

Phase 5 — Production rollout
- Enable feature flag to true in production and monitor.

Operational flows and semantics
------------------------------
- One session → one Draft Workspace
  - Created at session start; stored in state under `draft_workspace_id` and in SessionPersistence.
- All future file edits stored in Draft Workspace
  - Nodes produce deltas; DraftWorkspaceService.apply_edit stores file versions.
  - DiffEngine produces per-change diffs stored in `draft_change_history` in state.
- Discard last change uses SnapshotEngine
  - Use SnapshotEngine.restore(draft_id, last_snapshot_id) to revert.
- Session history restored after restart
  - On resume, graph checkpoint restores `GlueJobState` (including `draft_workspace_id`); processor can query DraftWorkspaceService for file metadata and SnapshotEngine for snapshot history.

Backwards compatibility / no breaking changes
--------------------------------------------
- All new state fields are optional. If `ENABLE_STATE_V2` is false or field missing, nodes fall back to current behavior (read `terraform_hcl` and `files_to_modify` from state).
- Use feature flag to gate behavior and provide immediate rollback.
- Keep existing LangGraph edges, interrupts, and node semantics unchanged to avoid breaking front-end expectations.

Risks
-----
1. Data consistency & race conditions
   - Multiple concurrent edits could conflict: ensure DraftWorkspaceService.apply_edit is atomic and returns authoritative version ids.
   - When graph auto-advances and simultaneously an inline edit comes in, there may be ordering subtleties; use thread_config and graph.aupdate_state to serialize.

2. Checkpoint size
   - Storing large file content inside LangGraph checkpoints will bloat storage. Solution: only store small metadata and keep file contents in DraftWorkspaceService.

3. Performance
   - Extra network / I/O when DraftWorkspaceService calls are remote or heavy (S3). Introduce an in-memory DraftCache for latest session activity.

4. Snapshot storage costs
   - Frequent snapshots increase storage costs. SnapshotEngine should support incremental snapshots or deduplication.

5. Rollout complexity
   - Frontend and backend must align: UI must read preview content from DraftWorkspaceService. Rollout must coordinate both.

6. Recovery complexity
   - If DraftWorkspaceService is unavailable during session restore, sessions cannot show previews; ensure graceful degradation (fall back to checkpointed last-known content if present).

Rollback strategy
-----------------
- Feature-flagged rollout (ENABLE_STATE_V2) — revert to previous behavior by toggling flag off.
- Keep code paths for both modes concurrently during rollout.
- Migration steps are additive (optional fields) — rolling back only requires disabling DraftWorkspace writes; existing drafts remain accessible by session id.
- If major issue occurs:
  1. Flip `ENABLE_STATE_V2 = False` in runtime config.
  2. Stop routing file edits to DraftWorkspaceService and continue using checkpointed `terraform_hcl` state.
  3. Optionally: export Draft Workspace content to a temporary location for manual recovery.

Monitoring, metrics, and observability
-------------------------------------
- Track metrics:
  - DraftWorkspace creates per-hour / per-session
  - DiffEngine diffs recorded per change
  - SnapshotEngine snapshot duration and storage growth
  - Latency: DraftWorkspace apply_edit time
  - Errors: DraftWorkspace apply failures, Snapshot restore failures
- Add audit entries for each apply_edit and snapshot via `AuditLog`.

Open design questions / decisions
--------------------------------
1. Draft workspace storage backend
   - S3-like object store with path-versioning vs. Git-backed local repo vs. ephemeral file system. Choose based on existing `DraftWorkspaceService` implementation.
2. Transaction model for multi-file edit groups
   - When `generate_terraform` emits multiple files, should it be one atomic change with one snapshot? Recommended: group edits per node run into one transaction and one snapshot.
3. When to garbage-collect draft workspaces?
   - Session TTL via SessionPersistenceService; garbage collect drafts after TTL + grace window. Provide admin cleanup.

Actionable next steps (developer tasks)
---------------------------------------
1. Add `ENABLE_STATE_V2` config flag and wire service initializers in `main.py` lifespan.
2. Add optional fields to `GlueJobState` in `state.py`.
3. Implement `processor` hooks:
   - Create draft on new session.
   - Route node file deltas to DraftWorkspaceService.apply_edit.
   - Record diff and snapshot metadata into state via `graph.aupdate_state`.
4. Update nodes that output file contents to emit structured file-edit deltas.
5. Update UI endpoints/preview to read from DraftWorkspaceService.
6. Add tests exercising session restart, discard last change, grouped edits, and concurrent edits.

Appendix — Example data flows
----------------------------
- New session
  - `process_first_message(session_id)` → `DraftWorkspaceService.create(session_id)` -> initial state with `draft_workspace_id` → graph resumes.
- generate_terraform node
  - Node returns: `{"terraform_hcl": "...", "files_to_modify": ["locals.tf"], "file_edits": [{"path":"saptcc/locals.tf","content":"..."}]}`
  - Processor sees `file_edits` → `DraftWorkspaceService.apply_edit(draft_id, path, content, meta)` → returns `change_id` → call `DiffEngine.record(change)` and `SnapshotEngine.capture(draft_id, change_id)` → update state `draft_change_history` with returned metadata via `graph.aupdate_state`.
- Discard last
  - UI triggers discard -> API calls `SnapshotEngine.restore(draft_id, previous_snapshot_id)` -> update `draft_change_history` and checkpoint state.

End of plan.
