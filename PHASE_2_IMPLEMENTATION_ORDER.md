PHASE 2 IMPLEMENTATION ORDER
Date: 2026-06-12

Priority order (as requested) with concise implementation steps, prerequisites, dependencies, and rough effort estimates.

1) Repository Topic Validation
- Goal: Make repository the authoritative source for topic/schema_grain existence.
- Tasks:
  - Implement new node `validate_topic_in_repository_node` (or extend `check_kafka_topic_node`) to:
    - Build expected topic name (env.source.schema_grain.raw)
    - Use `GitHubService` to read `confluent_minerva_dev/topics_<source>.tf` (base branch)
    - Parse file or grep for `schema_grain` entry
    - If not found: return blocking assistant_message: "Please create the topic first." and set route to `STEP_COLLECT_TOPIC` (block)
  - Add unit tests: file present/absent, schema present/absent, file missing
- Prereqs: `GitHubService.get_file_content()` already exists
- Estimated effort: 4–6 hours
- Depends on: none (high priority)

2) Existing vs New Source System Logic
- Goal: Ensure source-system branching logic matches rules (existing → locals.tf only; new → locals.tf + glue.tf)
- Tasks:
  - Consolidate `GitHubService.get_source_system_repository_state()` logic to check canonical `confluent_minerva_dev/topics_*.tf` and `{source}/locals.tf` consistently
  - Ensure nodes that decide `source_system_exists` rely on `GitHubService` (repo) not KB
  - Lock node behaviors: existing → only modify `locals.tf`; new → create both files
  - Add defensive unit tests around `_commit_existing_system` and `_commit_new_system`
- Prereqs: Step 1 implemented
- Estimated effort: 3–5 hours
- Depends on: Repository Topic Validation

3) Create Another Glue Job visibility
- Goal: Backend-driven menu visibility: only show "Create Another Glue Job" after a draft contains >=1 glue job.
- Tasks:
  - Add `glue_jobs_created_count` or use `draft['glue_jobs']` length in session summary returned by `SessionPersistenceService.get_session_summary()` and `DraftWorkspaceService.get_summary()`.
  - Update `processor` or next-step API to include `menu_options` computed server-side.
  - Frontend: render menu options from API payload (conditional display). Add unit tests for visibility.
- Prereqs: Draft workspace wiring (exists in services)
- Estimated effort: 1.5–3 hours
- Depends on: Draft Workspace integration (partial)

4) Draft Workspace integration with LangGraph
- Goal: Wire per-session Draft Workspace into LangGraph runtime so node file deltas are stored in draft and snapshot/diff recorded.
- Tasks:
  - On session creation (`process_first_message`), call `SessionPersistenceService.create_draft_for_session()` and attach `draft_id` to initial LangGraph state (optional field) and persist.
  - Modify nodes that produce file content (`generate_terraform_node`, `terraform_preview_node`) to emit `file_edits` deltas (list of {path, content}). Update `processor` to capture node deltas and call `DraftWorkspaceService.add_file()` / `add_glue_job()` rather than embedding large content in state.
  - Record diffs: after apply_edit, call `SnapshotManager.create_auto_snapshot()` (Draft service already auto-snapshots) and capture `changeset` via `SnapshotEngine.get_changeset_between()` and store minimal metadata in state (e.g., `draft_change_history` entries).
  - Ensure `process_user_message` uses `DraftWorkspaceService.get_file()` for previews instead of `terraform_hcl` when feature flag enabled.
  - Add integration tests covering session restart, discard last change, and grouped multi-file edits.
- Prereqs: DraftWorkspaceService, SnapshotEngine, DiffEngine exist (Phase 1)
- Estimated effort: 8–16 hours
- Depends on: Steps 1–3 for correct repo validation and menu UX

5) One PR = One Commit
- Goal: Create PRs with a single consolidated commit containing all file changes.
- Tasks:
  - Replace per-file `_create_or_update_file()` calls with a single tree/commit creation flow:
    - Collect all file blobs (new/modified) into a tree
    - Create a single commit with message
    - Update branch ref to point to commit (create ref if missing)
  - Use PyGithub low-level Git Data API or shell out to Git as needed; add tests that verify PR contains single commit with expected tree entries.
- Prereqs: Draft workspace content composed and accessible; GitHubService privilege for tree/commit APIs
- Estimated effort: 3–5 hours
- Depends on: Draft Workspace integration (files prepared), Repository Topic Validation (to know what to commit)

6) Conflict Resolution
- Goal: Detect conflicts between draft branch and base branch, present diffs, allow resolution strategies, apply amend & force-push.
- Tasks:
  - After branch creation, compare base branch sha to recorded base sha; attempt merge or detect divergence.
  - Use DiffEngineService.has_conflicts() (implement real detection) to detect conflicting hunks.
  - Add API endpoints: `POST /api/conflicts/detect` and `POST /api/conflicts/resolve` to return structured conflicts and accept resolution choices.
  - Implement backend resolution apply: transform files per selection, create amended commit (single commit), and force-push with `force-with-lease` semantics.
  - Add UI conflict resolution component (GitHub-style choices) to accept user selection and submit to resolve endpoint.
- Prereqs: One PR = One Commit implemented, Git tree/commit support
- Estimated effort: 6–10 hours
- Depends on: Steps 1,4,5

7) Diff Review UI
- Goal: Provide GitHub-style diff view for draft workspace with Added/Removed/Changed coloring.
- Tasks:
  - Backend: expose endpoint `GET /api/drafts/{draft_id}/changeset` returning `changeset` (DiffEngineService.format_changeset_for_ui() + structured file diffs)
  - Frontend: implement diff viewer component that renders file hunks with green (added), red (removed), and inline context; support job-level changes summary.
  - Integrate into Review screen and PR creation flow.
- Prereqs: DiffEngineService producing changesets (exists), Draft Workspace integration
- Estimated effort: 6–10 hours (backend + frontend)
- Depends on: Steps 4–6

8) React Vite ChatGPT UI (UX polish)
- Goal: Update frontend chat UI to minimal-question flow and integrate Review/Conflict UI.
- Tasks:
  - Modify chat flows to ask only Environment, Source System, Schema Grain; defer other fields to Draft Review.
  - Add Review screen showing diffs and conflict-resolution UI.
  - Ensure Vite dev setup and build scripts updated; add e2e smoke test for workflow.
- Prereqs: Backend endpoints for draft, diffs, conflicts
- Estimated effort: 6–12 hours
- Depends on: Steps 3–7

Notes on rollout & feature flags
- Use `ENABLE_STATE_V2` feature flag and `ENABLE_DRAFT_WORKSPACE` to gate behavior during rollout.
- Implement backwards-compatible optional fields in `GlueJobState` (`draft_workspace_id`, `draft_change_history`, `last_snapshot_id`) to allow easy rollback.
- Rollout plan: enable in staging behind flag; run integration tests and manual QA; enable for small percentage / internal users; monitor metrics and errors.

End of Phase 2 implementation order.
