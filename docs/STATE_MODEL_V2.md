# STATE_MODEL_V2 — LangGraph State Model for MIF Infrastructure Copilot

Purpose
-------
This document defines the complete state model (V2) used by the LangGraph orchestrator and backend services to support ChatGPT-style sessions, Draft Workspace, repository navigation, multi-file edits, multi-Glue-job creation, validation pipelines, auto-derived values, GitHub OAuth flows, PR creation, and session restoration.

Goals
-----
- Provide a single source-of-truth state definition for session lifecycle and persistence.
- Make state easy to snapshot, diff, restore, and audit.
- Support concurrent users and long-running background tasks (validation, plan, external queries).
- Ensure derivation provenance and editability are surfaced.

Storage & Persistence Strategy
------------------------------
- Primary metadata store: Postgres (relational) for sessions, messages, draft file metadata, glue job metadata, derivation records, PR records, user profiles.
- Ephemeral fast state: Redis for ephemeral session locks, transaction caches, job queues, optimistic locks, and rate-limiting tokens.
- Large artifact storage: Object store (S3 or local object store) for draft file contents, generated Glue scripts, and terraform plan artifacts. Stored with URI references in DB.
- Full-text search / indexing: Elastic/Opensearch (or Postgres GIN) for repository search and KB lookup caches.
- Audit log: append-only JSONL files in `logs/audit.jsonl` and optionally streamed to object store/ELK.

Primary Entities & Schemas
--------------------------
All IDs are UUIDv4 unless noted.

1) UserProfile
---------------
- id: UUID
- username: string (github login)
- display_name: string
- email: string
- oauth_provider: enum {github}
- oauth_tokens: JSONB reference(s) (token metadata stored encrypted in DB or a secrets store)
- roles: string[] (user roles for admin/maintainer)
- created_at, updated_at: timestamps

2) Session
-----------
Represents a ChatGPT-style session.
- id: UUID
- user_id: UUID (FK -> UserProfile)
- title: string (user editable)
- environment: enum {DEV, PROD}
- status: enum {active, paused, closed, pr_created, archived}
- created_at, updated_at, last_activity_at: timestamps
- current_draft_id: UUID (FK -> DraftWorkspace)
- message_count: int
- git_context: JSONB {repo: string, branch: string (target), fork: optional, base_ref: string}
- oauth_token_ref: reference to token in encrypted store (nullable)
- provenance: JSONB [] (list of derivation ids used in initial suggestions)
- version: integer (state model version)

3) Message
----------
Represents chat transcript messages.
- id: UUID
- session_id: UUID
- sender: enum {user, assistant, system}
- content: text (markdown/plain) — the user-visible text
- actions: JSONB [] (ActionCard descriptors: e.g., {type: 'apply_draft', label:'Apply Draft', payload:{...}})
- metadata: JSONB (timestamps, source node references, derivation_ids)
- created_at, edited_at: timestamps

4) DraftWorkspace
------------------
Holds draft files and Glue jobs for a session.
- id: UUID
- session_id: UUID
- created_by: UUID
- created_at, updated_at
- files_index: JSONB {path -> DraftFileMetadata} (redundant index cached for fast UI listing)
- change_sets: JSONB[] (ordered list of ChangeSet summaries)
- glue_jobs_index: JSONB {job_key -> GlueJobSummary}
- terraform_preview_id: UUID (reference to last plan artifact in Object store)
- validation_reports: JSONB[] (summary entries of last validations)
- snapshot_refs: JSONB[] (list of stored snapshot object URIs)
- locked_by: UUID nullable (session lock for multi-tab edit safety)

5) DraftFileMetadata
---------------------
- file_id: UUID
- path: string (workspace relative)
- sha: string (content hash, e.g., SHA256)
- size_bytes: int
- updated_by: UUID
- updated_at: timestamp
- stored_uri: string (object store path)
- diff_summary: JSONB (lines added/removed)
- status: enum {added, modified, deleted, unchanged}

6) DraftFileContent (object store artifact)
------------------------------------------
- stored_uri: string
- content: blob
- content_type: string
- created_at
- metadata: JSONB {file_id, path, session_id}

7) ChangeSet
------------
- id: UUID
- draft_id: UUID
- author_id: UUID
- created_at
- commit_message: string (user-editable)
- files: array of {file_id, path, action: added/modified/deleted, before_sha (nullable), after_sha}
- validated: boolean
- validation_summary_id: UUID (nullable)

8) GlueJobSummary & GlueJobDefinition
------------------------------------
Summary (in index):
- job_id: UUID
- job_key: string (glue logical name)
- display_name: string
- source_type: enum {kafka,jdbc,flat_file,api}
- schedule: {type: manual|scheduled, nl: string|null, cron: string|null}
- status: enum {draft, validated, validation_failed}
- created_at, updated_at

Definition (full):
- job_id: UUID
- draft_id: UUID
- definition: JSONB (complete module inputs and glue_job_arguments)
- generated_artifacts: JSONB (list of stored_uri for glue scripts, terraform snippet)
- derivations: array of DerivationEntry ids
- validation_reports: array of ValidationReport ids

9) DerivationEntry
-------------------
Records every auto-derived value with provenance and confidence.
- id: UUID
- session_id: UUID
- key: string (e.g., `topic_name`, `glue_job.worker_type`)
- derived_value: string/JSON
- source: string (knowledge_base path or node id) e.g., `knowledge_base/terraform_template.json#L12`
- confidence: enum {HIGH, MEDIUM, LOW}
- editable: boolean
- visibility: enum {shown, advanced, hidden}
- timestamp
- user_edited: boolean
- edit_history: JSONB[] (previous values, who edited, timestamp)

10) ValidationReport
---------------------
- id: UUID
- draft_id: UUID
- type: enum {kafka_topic, schema_registry, terraform_plan, tfsec, custom}
- target: JSONB (what was validated: file paths, glue job id, topic name)
- status: enum {pending, success, warn, failed}
- summary: string
- details_uri: string (object store link to logs/artifacts)
- started_at, finished_at
- created_by_node: string (LangGraph node id)

11) PRRecord
-------------
- id: UUID
- session_id: UUID
- draft_id: UUID
- repo: string
- fork: string
- branch: string
- pr_number: int nullable
- pr_url: string nullable
- created_by: UUID
- created_at
- status: enum {created, merged, closed}
- summary: JSONB (files changed, glue jobs included, validation snapshot)

12) LangGraphNodeState
----------------------
Per-node transient state for orchestration and resuming.
- node_id: string
- session_id: UUID
- status: enum {idle, running, failed, completed}
- input_payload: JSONB
- output_payload: JSONB
- started_at, completed_at
- retry_count
- error_message

13) BackgroundTask / QueueJob
-----------------------------
Used for long-running ops
- id
- session_id
- task_type {terraform_plan, tfsec_scan, kafka_check, schema_fetch}
- status {queued, running, succeeded, failed, cancelled}
- worker_id
- logs_uri
- started_at, finished_at


State Lifecycle & Transitions
-----------------------------
High-level lifecycle for a session and its draft workspace:

1) Creation
- User opens UI and selects `Environment` (DEV/PROD) -> create `Session` (status=active) and `DraftWorkspace` (status implicit)
- first `DerivationEntry` records initial auto-derived values

2) Interaction / Iteration
- User sends messages -> `Message` created, LLM node produces assistant messages and ActionCards.
- Actions (Apply Draft, Edit File, Add Glue Job) mutate `DraftWorkspace` and create `ChangeSet` entries and `DraftFileMetadata` updates. Each mutation produces DerivationEntry records for any derived values used.
- Optimistic concurrency: edits acquire a short Redis lock for the session/draft; write operations update Postgres and object store.

3) Validation Phase
- User (or assistant) triggers `Run Plan` -> enqueue BackgroundTask terraform_plan -> Task runs, writes artifacts to object store -> Task updates ValidationReport(s) and DraftWorkspace.validation_reports.
- ValidationReport status transitions from pending -> success|warn|failed. UI reflects badges.

4) PR Creation
- User triggers `Create PR` -> system assembles ChangeSets -> prepares commits -> GitHub Node creates fork/branch and commits (requires oauth_token_ref)
- Create `PRRecord` with status `created` and update session.status to `pr_created`.

5) Session close / Archive
- After PR merge or user action, session.status -> closed or archived. DraftWorkspace snapshots can be persisted for N days then garbage collected.

State Transition Table (selected)
---------------------------------
- Session.status: active -> paused (user action) -> active (resume)
- active -> pr_created (on PR creation)
- pr_created -> closed (when PR merged or closed)
- DraftFile.status: unchanged -> modified -> staged -> included_in_changeset -> committed
- ValidationReport: pending -> success|warn|failed -> resolved (when user addresses) or archived

Concurrency & Locking
----------------------
- Short-term edit locks in Redis: per-session and per-file locks (ttl ~ 30s) for live collaborative protections.
- Long-running operations (terraform_plan) use optimistic locking: store plan artifact id and current draft_sha; if draft changed during plan, mark plan as stale and require re-run.
- Multi-tab: client receives `session_version` in session object; each mutation increments version. Client detects version mismatch and can prompt reload or reconcile.

Snapshots & Restore
-------------------
- Snapshot strategy: on major events (apply draft, run validations, PR creation) create DraftWorkspace snapshot (store files as archive in object store) and a snapshot record in DB with timestamp and pointer.
- Restoration: user selects a snapshot -> system replaces DraftWorkspace.files_index and ChangeSet ordering with snapshot data and records an audit event.

Derivation Provenance & Edit Tracking
------------------------------------
- Every auto-derived value must have a DerivationEntry referencing its source and confidence.
- If user edits a derived value, set DerivationEntry.user_edited=true and append to edit_history. Downstream nodes should prefer user_edited values over fresh derivations.

Validation Data Model (details)
-------------------------------
- ValidationReport.details stored as structured JSON when possible: e.g., terraform_plan_summary {resources_added, changed, destroyed} and tfsec_issues [{id, severity, rule, path, message}].
- For large logs, ValidationReport.details_uri points to object store artifact with full logs.

Schema for UI Efficiency (cached projections)
-------------------------------------------
To support fast UI, store denormalized projections:
- SessionListProjection: basic session metadata for left sidebar.
- DraftOverviewProjection: derived counts (files changed, glue jobs, validations) for right sidebar.
- PRPreviewProjection: combined summary for PR Review screen.

Security and Secrets Handling
----------------------------
- OAuth tokens: stored encrypted, with short TTLs and refresh process. Backend should never expose raw tokens in logs.
- Secrets referenced in jobs (secret names) are referenced by name only; actual secret values must be retrieved by CI/deployment or the user when necessary. UI never displays secret values.

Retention & Garbage Collection
------------------------------
- Snapshots retained for configurable TTL (default 30 days).
- DraftWorkspaces with no activity for > 90 days moved to archive and then purged after an additional TTL.
- Audit logs retained per org policy; keep at least 1 year.

Eventing & Notifications
------------------------
- Important state changes emit events to message bus (Redis/Stream or Kafka) to notify UI and workers: session.updated, draft.updated, validation.completed, pr.created.
- WebSocket / SSE push to client with minimal payloads (ids and statuses) and client can fetch full projection.

Error Handling Patterns
-----------------------
- Node failures captured in LangGraphNodeState with error_message and retry_count. Node can be retried with exponential backoff; persistent failures are surfaced in assistant messages with actionable steps.
- Stale plan detection: when draft changed during plan run, mark plan `stale=true` and require re-run.

Operational Considerations
--------------------------
- Migration: version field on Session supports schema migrations; migration scripts to backfill derivation entries from existing derive_values outputs.
- Backups: Postgres + object store backup strategy recommended (daily snapshots + WAL archiving).

API Contracts (high-level)
--------------------------
- `POST /sessions` -> create session with env and user_id -> returns Session projection.
- `GET /sessions/:id` -> full session including messages and draft summary.
- `POST /sessions/:id/messages` -> append Message and return assistant response (async orchestration via LangGraph).
- `PATCH /drafts/:draft_id/files` -> update file contents (uploads object store content), returns updated DraftFileMetadata and new ChangeSet id.
- `POST /drafts/:draft_id/validate` -> enqueue validation job(s); returns ValidationReport ids.
- `POST /sessions/:id/create-pr` -> attempt PR creation (requires oauth) -> returns PRRecord.

Versioning & Extensibility
--------------------------
- Each major state change increments `session.version` and uses optimistic concurrency with `WHERE version = :expected` updates.
- LangGraph nodes accept `session_id` and `draft_id` and return structured outputs referencing DerivationEntry ids and ValidationReport ids.

Examples (walkthrough)
----------------------
1) User starts session (DEV) -> session created; DerivationEngine populates topic_name, glue_job_name -> entries saved as DerivationEntry.
2) User applies draft -> files uploaded to object store, DraftFileMetadata created, ChangeSet created.
3) User runs plan -> BackgroundTask spawned, validation_report pending -> on completion validation_report updated and linked to draft.
4) User creates PR -> PRRecord created, session.status updated to pr_created, audit log appended.

Appendix: Minimal JSON shape examples
-----------------------------------
(Omitted here for brevity — implementers should use the above schema field names and types.)

Next Steps
----------
- Review this model with the LangGraph implementer and DB architect; produce SQL schema migrations and object store key patterns.
- Define DerivationEngine API and LangGraph node adapters to persist DerivationEntry and LangGraphNodeState.
