FINAL IMPLEMENTATION BASELINE — Reconciliation Audit
Date: 2026-06-12

Purpose
-------
Reconcile the Architecture Freeze Rules against: Phase 1 implementation, FINAL_GAP_ANALYSIS.md, PHASE_1_AUDIT_REPORT.md, and PHASE_1_FINAL_VERIFICATION.md. For each Architecture Rule (1–19) present: Status, Evidence (exact files, classes, methods), and concise note.

1) Repository Topic Validation — validate schema_grain inside `confluent_minerva_dev/topics_<source>.tf`
Status: Not Implemented
Evidence:
- `backend/app/graph/nodes/check_kafka_topic.py` — function `check_kafka_topic_node(state: GlueJobState)` uses `KafkaService.check_topic_exists()` and `KafkaService.get_schema_count()`; no repository file lookup.
- `backend/app/services/github_service.py` — class `GitHubService` contains `get_source_system_repository_state()` and `get_source_system_repository_state()` reads `{source}/locals.tf` but does NOT read `confluent_minerva_dev/topics_<source>.tf` or search for `schema_grain`.
Note: No code inspects `confluent_minerva_dev/topics_*.tf` for `schema_grain` presence.

2) Do not use Kafka as authoritative validation
Status: Not Implemented
Evidence:
- `backend/app/graph/nodes/check_kafka_topic.py` — `check_kafka_topic_node` relies on `KafkaService.check_topic_exists()` and `KafkaService.get_schema_count()` (broker + Schema Registry checks) as primary checks.
- `backend/app/services/kafka_service.py` — class `KafkaService` implements `check_topic_exists()` and `get_schema_count()` used by node above.
Note: No repository-first override present in the node; Kafka is currently authoritative in decision flow.

3) If `schema_grain` not found: "Please create the topic first." (blocking)
Status: Not Implemented
Evidence:
- `backend/app/graph/nodes/check_kafka_topic.py` — when topic is missing the node returns an assistant_message instructing to verify topic exists in Kafka broker (error text: "Please verify the topic exists in the Kafka broker and try again.") — not the repository-first blocking message requested.
- `backend/app/api/processor.py` — synthesizes approval/approval_request messages but does not contain a repository-based blocking message.

4) Existing Source System — Only modify `/locals.tf`
Status: Partially Implemented (server-side code enforces locals.tf update)
Evidence:
- `backend/app/services/github_service.py` — class `GitHubService` method `_commit_existing_system(self, repo, branch_name, state, locals_path)` reads `{locals_path}` and calls `_insert_into_glue_jobs()` then `_create_or_update_file()` for the single `locals_path`. It does NOT modify `glue.tf` for existing sources.
Note: Code enforces modifying `locals.tf` only; docs may contradict and must be aligned.

5) Never modify `glue.tf` automatically
Status: Partially Implemented / Not Implemented (depends on interpretation)
Evidence:
- `backend/app/services/github_service.py` — method `_commit_new_system(self, repo, branch_name, state)` creates both `locals.tf` and `glue.tf` for new source systems via `_create_or_update_file()` (lines creating `locals_path` and `glue_path`).
Note: If the rule forbids any automatic `glue.tf` creation, current code violates it for new source systems.

6) New Source System — Create: `locals.tf` and `glue.tf`
Status: Implemented
Evidence:
- `backend/app/services/github_service.py` — method `_commit_new_system(self, repo, branch_name, state)` creates `locals.tf` and `glue.tf` using `state['locals_tf_full']` and `state['glue_tf_content']` via `_create_or_update_file()`.

7) Create Another Glue Job — visible only after at least one glue job exists in current session
Status: Not Implemented
Evidence:
- `backend/app/graph/state.py` — `GlueJobState` TypedDict and `initial_state()` do NOT include a `glue_jobs_created_count` or equivalent field.
- Frontend menu rendering: docs reference in `docs/REPOSITORY_NAVIGATOR.md` but no evidence of server-side conditionalization in API responses (no API method in `backend/app/api/processor.py` exposes menu visibility based on session state).

8) One Session = One Draft Workspace
Status: Partially Implemented
Evidence:
- `backend/app/services/session_persistence.py` — class `SessionPersistenceService`: method `create_draft_for_session(self, session: Session) -> DraftWorkspace` calls `self.draft_service.create_draft(session['session_id'])` and stores `session['current_draft_id']`.
- `backend/app/services/draft_workspace_service.py` — class `DraftWorkspaceService`: method `create_draft(self, session_id: str) -> DraftWorkspace` creates draft and auto-snapshots via `SnapshotManager.create_auto_snapshot()`.
- Missing integration point: `backend/app/api/processor.py` (LangGraph processor) does not call `create_draft_for_session()` on `process_first_message()` — no clear automatic creation on session start. Therefore one-session→one-draft exists at services layer and tests, but not fully wired into the LangGraph runtime.

9) One PR = One Commit
Status: Not Implemented
Evidence:
- `backend/app/services/github_service.py` — class `GitHubService`: methods `_create_or_update_file()` call `repo.update_file()` / `repo.create_file()` per file. `_commit_existing_system()` and `_commit_new_system()` call `_create_or_update_file()` once per file, resulting in multiple commits. No method aggregates files into a single tree/commit before creating the PR.

10) Discard Last Change — Snapshot based
Status: Implemented (service-level)
Evidence:
- `backend/app/services/snapshot_engine.py` — class `SnapshotEngine`: method `discard_last_change(self, draft_id: str) -> Optional[Snapshot]` returns previous snapshot; `restore_snapshot()` exists.
- `backend/app/services/snapshot_engine.py` — class `SnapshotManager`: method `undo_last_operation(self, draft_workspace: DraftWorkspace) -> bool` applies `discard_last_change()` and restores draft state.
- `backend/app/services/draft_workspace_service.py` — method `discard_last_change(self, draft: DraftWorkspace) -> bool` calls `self.snapshot_manager.undo_last_operation(draft)`.
Note: Snapshot-based discard is implemented at service layer.

11) Snapshots hidden from users
Status: Implemented (service-level)
Evidence:
- `backend/app/services/snapshot_engine.py` and `backend/app/services/draft_workspace_service.py` implement snapshot creation and management.
- No FastAPI endpoints found exposing raw snapshot lists or snapshot objects in `backend/app/api/` (grep: no API handlers returning snapshots). Phase 1 audit notes snapshots are backend-only.

12) Conflict Resolution — Incoming vs Current changes
Status: Not Implemented
Evidence:
- `backend/app/services/diff_engine.py` — class `DiffEngineService` includes `has_conflicts(changeset: ChangeSet) -> bool` which contains a `# TODO: Implement conflict detection` and returns `False`.
- `backend/app/services/github_service.py` — class `GitHubService` does not implement conflict detection/merge logic around branch creation/merges; no conflict endpoints exist.

13) User selects resolution
Status: Not Implemented
Evidence:
- No backend endpoints found to accept conflict-resolution choices (no `conflicts/resolve` API in `backend/app/api/`).
- No frontend UI components in `frontend/src/` that implement a conflict-resolution flow (grep for conflict UI returned no results).

14) Commit amend
Status: Not Implemented
Evidence:
- `backend/app/services/github_service.py` — uses high-level `repo.update_file()` and `repo.create_file()`; no use of Git low-level tree/commit APIs to amend a single commit. No `_amend_commit()` method exists.

15) Force push
Status: Not Implemented
Evidence:
- `backend/app/services/github_service.py` — method `create_pr()` uses `repo.create_git_ref()` and PyGithub `create_file` / `update_file` but does not perform force-push or amend with `force=True`. No direct git push functionality exists.

16) Draft Workspace Review — GitHub-style diff view
Status: Partially Implemented
Evidence:
- `backend/app/services/diff_engine.py` — `DiffEngineService.format_changeset_for_ui()` and `get_diff_summary()` provide server-side formatting utilities.
- No API endpoints in `backend/app/api/` that return a changeset or formatted diff for a draft (grep for `diff` in `backend/app/api` returned none).
- Frontend diff UI not present (no dedicated diff viewer component found in `frontend/src/components/` by grep).

17) Added = Green (diff coloring)
Status: Not Implemented (UI)
Evidence:
- `backend/app/services/diff_engine.py` formats strings (emoji-based), but no frontend color rendering implemented.

18) Removed = Red (diff coloring)
Status: Not Implemented (UI)
Evidence:
- Same as rule 17.

19) ChatGPT-style UX — Minimal questions limited to Environment, Source System, Schema Grain
Status: Partially Implemented
Evidence:
- `backend/app/api/processor.py` — `_map_user_input_to_state()` restricts mapping to focused steps (`STEP_COLLECT_TOPIC`, `STEP_DERIVE_VALUES`, `STEP_COLLECT_WORKERS`, etc.).
- `backend/app/graph/state.py` — `GlueJobState` contains many fields (sink, workers, schedule) that are currently collected through nodes like `collect_sink_node` and `collect_workers_node` (see `app/graph/nodes/collect_sink.py`, `collect_workers.py`).
Note: KB defaults are used (see `initial_state()` referencing `get_knowledge_base()`), but several fields are still requested during the workflow. Minimization requires deferring fields to Draft Workspace Review.

Summary and next steps
----------------------
- Phase 1 implemented core Draft/Snapshot/Diff services and SessionPersistence, and unit tests exercise them (see `backend/tests/services/*`).
- Critical gaps remain: repository-first topic validation (Rule 1–3), PR commit consolidation (Rule 9), conflict detection & resolution (Rule 12–15), and UI integration for diffs and conflict resolution (Rules 16–18).
- Many service-level building blocks for Phase 2 exist (DraftWorkspaceService, SnapshotEngine, DiffEngine, SessionPersistenceService), but wiring into the LangGraph runtime and PR workflow is incomplete.

End of baseline.
