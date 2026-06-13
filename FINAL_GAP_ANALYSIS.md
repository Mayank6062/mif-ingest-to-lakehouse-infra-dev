FINAL GAP ANALYSIS — Architecture Freeze Rules
Date: 2026-06-12

Summary
-------
This document validates the current implementation in the repository against the mandatory Architecture Freeze Rules supplied by the product team. For each rule (1–19) the analysis reports: Compliance status, Severity (if non-compliant), Impact, Files affected, and an Estimated implementation effort (rough hours).

Legend
------
- Compliant: Implementation satisfies rule.
- Partial: Implementation covers parts of the rule or deviates in important ways.
- Not Implemented: Rule absent or contradicts current behavior.

1) Repository Topic Validation — validate schema_grain inside confluent_minerva_dev/topics_<source>.tf
- Status: Not Implemented
- Severity: 🔴 Critical
- Impact: Agent currently trusts Kafka/Schema Registry. Without repository-driven checks, agent may accept topics that are not authorized in Terraform, causing orphan or out-of-sync infra changes.
- Files affected: backend/app/graph/nodes/check_kafka_topic.py, backend/app/services/github_service.py (read access), docs/ARCHITECTURE_FREEZE_REVIEW.md
- Estimated effort: Large (4–6 hours)

Notes: The current node `check_kafka_topic_node` only checks Kafka+SR (broker + registry). No logic exists to locate or parse `confluent_minerva_dev/topics_*.tf` in the repo. Implementation requires reading repo file(s) (via GitHubService), parsing or grepping for `schema_grain`, and making repository presence a blocking condition.

2) Do not use Kafka as authoritative validation
- Status: Not Implemented
- Severity: 🔴 Critical
- Impact: Current logic treats broker/topic existence as primary; this violates the authoritative-source rule (GitHub/Terraform). Risk of producing Terraform for topics absent in repo.
- Files affected: backend/app/graph/nodes/check_kafka_topic.py, backend/app/services/kafka_service.py
- Estimated effort: Medium (3–4 hours)

3) If schema_grain not found: "Please create the topic first." (blocking message)
- Status: Not Implemented / Partial
- Severity: 🔴 High
- Impact: User-facing messages are Kafka-oriented; must be replaced with a repository-first blocking response. UX and routing must route to topic creation guidance instead of auto-advance or approval dialogs.
- Files affected: backend/app/graph/nodes/check_kafka_topic.py, backend/app/api/processor.py (synthesised approval message), frontend message components
- Estimated effort: Small-Medium (1.5–3 hours)

4) Existing Source System — Only modify `/locals.tf`
- Status: Partial / Mostly Compliant
- Severity: 🟠 Medium
- Impact: Server-side `GitHubService._commit_existing_system` currently modifies only `locals.tf` for existing systems (good). However, other code paths or docs may suggest modifying `glue.tf` — ensure docs and nodes do not attempt to modify glue.tf.
- Files affected: backend/app/services/github_service.py (compliant), backend/app/graph/nodes/generate_terraform.py, docs/LANGGRAPH_V2_ARCHITECTURE.md
- Estimated effort (to verify and lock down): Small (1–2 hours)

Notes: Code correctly avoids editing `glue.tf` for existing sources. Ensure tests and docs reflect this rule; add explicit safeguards to prevent accidental glue.tf edits for existing sources.

5) Never modify glue.tf automatically
- Status: Partial
- Severity: 🟠 Medium
- Impact: For NEW source systems the service currently creates `glue.tf`. The rule phrasing is ambiguous — if interpreted as "do not auto-modify existing glue.tf", current code is compliant. If rule means "never create or modify glue.tf automatically under any case", then current code violates it (it creates glue.tf for new systems).
- Files affected: backend/app/services/github_service.py
- Estimated effort: Small (1 hour) to clarify rule intent and update code/docs.

Recommendation: Clarify whether creating `glue.tf` for new source systems is allowed (design doc earlier indicates creation is expected). If disallowed, change `_commit_new_system` to only create `locals.tf` and add manual operator task to add `glue.tf`.

6) New Source System — Create: locals.tf + glue.tf
- Status: Implemented (per current code)
- Severity: ✅ Compliant
- Impact: For new sources, `GitHubService._commit_new_system` creates both `locals.tf` and `glue.tf` from generated content.
- Files affected: backend/app/services/github_service.py
- Estimated effort: N/A (already implemented)

7) Create Another Glue Job — visible only after at least one glue job exists in current session
- Status: Not Implemented
- Severity: 🟠 High (UX / workflow correctness)
- Impact: UI likely shows option unconditionally. There's no session-level counter or `glue_jobs_created_count` in `GlueJobState` to drive conditional visibility.
- Files affected: backend/app/graph/state.py (missing field), frontend components (action/menu rendering), backend API output payloads
- Estimated effort: Small-Medium (1.5–3 hours)

8) One Session = One Draft Workspace
- Status: Not Implemented
- Severity: 🔴 Critical
- Impact: No Draft Workspace abstraction is present in the current runtime; file edits are committed directly to branches during PR creation rather than staged in a per-session draft workspace. This blocks snapshotting, discard, and a consistent draft editing UX.
- Files affected: many; proposed: backend/app/api/processor.py, backend/app/graph/state.py (new `draft_workspace_id`), services to implement: DraftWorkspaceService, SnapshotEngine, DiffEngine, SessionPersistenceService, and nodes that produce files (generate_terraform, create_pr, etc.).
- Estimated effort: Large (8–16 hours)

9) One PR = One Commit
- Status: Not Implemented
- Severity: 🔴 Critical
- Impact: Current `GitHubService` uses `_create_or_update_file` per file (PyGithub create/update). This results in multiple commits per PR. Requirement mandates a single consolidated commit per PR to comply with audit and traceability.
- Files affected: backend/app/services/github_service.py
- Estimated effort: Medium (3–5 hours)

10) Discard Last Change — Snapshot based
- Status: Not Implemented
- Severity: 🔴 High
- Impact: No SnapshotEngine or draft snapshot mechanism exists. Cannot implement discard/restore semantics without Draft Workspace + Snapshot capability.
- Files affected: service layer (new SnapshotEngine), processor hooks, UI endpoints
- Estimated effort: Large (6–10 hours)

11) Snapshots hidden from users
- Status: Not Implemented
- Severity: 🟠 Medium
- Impact: Snapshots do not exist. When implemented, snapshots must be an internal abstraction (not shown as separate objects in UI). Requires UI and API design.
- Files affected: frontend UI, snapshot engine, draft workspace metadata
- Estimated effort: Small (1–2 hours) to design and enforce hiding in API responses

12) Conflict Resolution — Incoming vs Current changes detection
- Status: Not Implemented
- Severity: 🔴 Critical
- Impact: No conflict detection or structured resolution UI exists. If concurrent repo changes happen, the PR flow may fail or silently overwrite changes.
- Files affected: backend/app/services/github_service.py, backend/app/api/processor.py, frontend conflict UI
- Estimated effort: Large (6–8 hours)

13) User selects resolution
- Status: Not Implemented
- Severity: 🔴 Critical
- Impact: Without a UI to let users pick Accept Incoming/Accept Current/Manual, conflict resolution cannot be performed safely. Requires backend endpoints and frontend UI.
- Files affected: backend endpoints (new), frontend components
- Estimated effort: Large (6–8 hours)

14) Commit amend
- Status: Not Implemented
- Severity: 🟠 High
- Impact: Required to produce an amended single commit after resolving conflicts or editing commit message. Current GitHubService relies on create/update file APIs; does not support low-level amend semantics.
- Files affected: backend/app/services/github_service.py
- Estimated effort: Medium (3–4 hours)

15) Force push
- Status: Not Implemented
- Severity: 🟠 High
- Impact: Required when amend needs to overwrite remote branch history; without force push the amend cannot be applied atomically. PyGithub high-level APIs may not offer direct force push — might require using Git data API or a Git client.
- Files affected: backend/app/services/github_service.py
- Estimated effort: Medium-Large (4–6 hours)

16) Draft Workspace Review — GitHub-style diff view
- Status: Not Implemented
- Severity: 🔴 High
- Impact: No server-side diff generation or UI to render GitHub-style diffs for draft workspace. This is central to review UX.
- Files affected: new DiffEngine service, frontend diff viewer, backend preview endpoints
- Estimated effort: Large (6–10 hours)

17) Added = Green (diff coloring)
- Status: Not Implemented
- Severity: 🟠 Medium
- Impact: Diff view not present; coloring is a UI concern controlled by frontend once diffs exist.
- Files affected: frontend components, diff generation APIs
- Estimated effort: Small (2–3 hours) once diff pipeline exists

18) Removed = Red (diff coloring)
- Status: Not Implemented
- Severity: 🟠 Medium
- Impact: Same as above. Requires diff generation + UI.
- Files affected: frontend components, diff generation APIs
- Estimated effort: Small (2–3 hours) once diff pipeline exists

19) ChatGPT-style UX — Minimal questions limited to Environment, Source System, Schema Grain
- Status: Partial
- Severity: 🟠 Medium
- Impact: Core `processor` and `state` already focus user input on specific steps. However some nodes and UI forms (collect_workers, collect_sink) expose many fields; these are prefilled from KB but still present. Achieving strict minimal-question UX requires hiding or deferring additional fields to Draft Workspace Review.
- Files affected: backend/app/api/processor.py, backend/app/graph/state.py, frontend form components
- Estimated effort: Small-Medium (2–4 hours)

Overall readiness verdict
------------------------
- Several critical requirements are NOT IMPLEMENTED: (1) repository-first topic validation, (2) not using Kafka as authoritative, (8) Draft Workspace per session, (9) One PR=One Commit, (10,12,13,16) snapshot/resolve/review flows.
- These gaps block production rollout if the Architecture Freeze Rules are mandatory. The most time-consuming work will be implementing a per-session Draft Workspace + Snapshot + Diff pipeline and the Git/PR changes to consolidate commits and support amend/force-push/conflict resolution.

Prioritized remediation estimate (rough):
- Implement Draft Workspace + Snapshot + Diff + Session metadata: 8–16 hours
- Implement repository-driven topic validation (search topics_*.tf): 4–6 hours
- Change GitHub PR flow to produce single-commit PRs + amend + force-push + conflict detection/UI: 8–12 hours
- UI work (diff viewer, conflict resolution): 6–10 hours
- Minor UI/backend UX alignment (create-another-job visibility, minimal questions): 2–4 hours

Total estimated engineering effort: ~28–48 hours (4–8 engineering days), depending on parallelization and reuse of libraries/clients.

Appendix — quick mapping to repo locations
-----------------------------------------
- Primary nodes to change: `backend/app/graph/nodes/check_kafka_topic.py`, `backend/app/graph/nodes/generate_terraform.py`, `backend/app/graph/nodes/create_pr.py`.
- Core services: `backend/app/services/github_service.py` (PR semantics), new services to add: `DraftWorkspaceService`, `SnapshotEngine`, `DiffEngine`, `SessionPersistenceService`.
- API layer: `backend/app/api/processor.py` (session creation hook, routing file deltas), `backend/app/main.py` (lifespan init for new services).
- State model: `backend/app/graph/state.py` (add optional fields: `draft_workspace_id`, `draft_change_history`, `last_snapshot_id`, `glue_jobs_created_count`).

End of analysis.
