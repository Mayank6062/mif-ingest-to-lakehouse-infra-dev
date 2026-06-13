# CONVERSATION_DESIGN — MIF Infrastructure Copilot

Purpose
-------
Design of a ChatGPT-style conversational interface that transforms the existing MIF Agent into an Infrastructure Copilot. Goals: minimize user questions, maximize automation, preserve correctness, provide a draft workspace, session history, multi-file and multi-Glue-job editing, and a single PR confirmation flow.

Notes on repository sources used while authoring this document
- Project-provided Glue process: [project_information/mif-glue-job-creation-terraform-script-process.md](project_information/mif-glue-job-creation-terraform-script-process.md#L1)
- Graph/orchestration entry points: [backend/app/graph/builder.py](backend/app/graph/builder.py#L1), [backend/app/graph/state.py](backend/app/graph/state.py#L1)
- API surface: [backend/app/api/routes.py](backend/app/api/routes.py#L1), [backend/app/api/processor.py](backend/app/api/processor.py#L1), [backend/app/api/websocket.py](backend/app/api/websocket.py#L1)
- Agents and services: [backend/app/agents/knowledge_agent.py](backend/app/agents/knowledge_agent.py#L1), [backend/app/agents/terraform_agent.py](backend/app/agents/terraform_agent.py#L1), [backend/app/services/github_service.py](backend/app/services/github_service.py#L1), [backend/app/services/terraform_validator.py](backend/app/services/terraform_validator.py#L1)
- Knowledge-base: [knowledge_base/source_systems.json](knowledge_base/source_systems.json#L1), [knowledge_base/terraform_template.json](knowledge_base/terraform_template.json#L1), [knowledge_base/validation_rules.json](knowledge_base/validation_rules.json#L1)
- Frontend to replace/migrate: [frontend/src/app/page.tsx](frontend/src/app/page.tsx#L1), [frontend/src/components/chat](frontend/src/components/chat#L1)

Design Principles
-----------------
- Environment selection is always the first action (DEV or PROD) and drives all derived values.
- Default-driven: prefer KB defaults; only ask clarifying questions when multiple KB options exist or values are ambiguous.
- Draft-first: edits are staged in a Draft Workspace until a single confirmation creates a PR.
- Session continuity: session history persists and behaves like ChatGPT (scrollable transcript, action buttons, editable assistant messages with applied/draft changes tied to session state).
- One final confirmation: the user confirms one PR creation action which bundles all changes.
- Modular nodes (LangGraph): one node = one responsibility (generate terraform, validate, create PR, generate Glue job, etc.).

Overview: high-level conversation flow
------------------------------------
1. User opens the Copilot UI (React + Vite SPA) and is prompted to select environment: `DEV` or `PROD`.
2. GitHub OAuth (if not authenticated) — handled via GitHub service; user grants minimal scopes.
3. User issues natural request (example: "Create Kafka ingestion for SourceX and two Glue jobs — hourly and daily").
4. Assistant (LLM Node) asks only clarifying questions if KB cannot derive required values.
5. Assistant generates draft artifacts (Terraform snippet, Glue job entries, Glue script templates, config changes) and stores them in session Draft Workspace.
6. Assistant runs validation (Terraform Plan Node, Terraform Validator Node, Schema/Topic checks) and reports results inline.
7. User iterates with edits or approves. User may edit files directly in the Draft Explorer UI.
8. When ready, user clicks `Create PR` — GitHub Node performs a single PR containing all staged changes.

1. End-to-end conversation flows
-------------------------------
Flow A (Create Kafka -> Glue job):
- Step 0: UI shows environment selector. User picks `DEV`.
- Step 1: User: "Add ingestion for AcmeCorp from Kafka, create Glue job to land raw data in Iceberg."
- Step 2: Assistant: resolves `source_system` (AcmeCorp) via KB, proposes topic name auto-generated as `dev.acmecorp.multi-1.raw` and shows derived Job Name & worker defaults. Minimal clarifying Q: "Confirm topic is for `AcmeCorp` and schedule: Manual or schedule?"
- Step 3: User selects `Schedule: hourly` using a dropdown. Assistant derives cron: `cron(0 * * * ? *)` and creates draft Glue job entry & Terraform snippet in Draft Workspace.
- Step 4: Assistant runs Topic existence validation, Schema Registry endpoint check, and Terraform Plan. Shows validation results.
- Step 5: User reviews diffs; optionally edits transformer options via UI controls.
- Step 6: User clicks `Create PR` — single PR is authored and opened in GH.

Flow B (Multiple Glue Jobs + multi-file edits):
- Steps: user adds second Glue job (e.g., daily dedupe job) and requests additional config file changes (e.g., add alerting). Assistant stages both jobs and file changes in the same draft. Single validation run merges validation across changes. Single PR bundles both jobs and file modifications.

2. Happy paths
-------------
- KB contains full defaults for source system and environment; assistant derives topic names, cron, secrets, Glue job args automatically; validations pass; user approves without typing.
- Multiple Glue jobs created in one session; user tweaks a parameter via simple dropdowns; PR created.

3. Failure paths
----------------
- Missing KB values: assistant asks a single targeted question and provides reasonable defaults; marks value as required in UI if user declines default.
- Terraform validation fails: assistant shows failing diff and inline plan logs, suggests fixes (e.g., missing assume-role ARN) and allows user to edit before PR.
- Topic absent: Topic existence validation returns not found — assistant offers to create topic or ask user to provide the topic (and provides auto-generated name).
- Schema Registry mismatch: assistant surfaces the schema count mismatch and suggests reconciliation options.

4. Validation paths
-------------------
- Topic existence validation: call to Kafka service (backend/app/services/kafka_service.py) per env; result: exists / not found / ambiguous -> present in UI.
- Schema Registry validation: check schema registry endpoint (KB provides endpoints per env); validate schema presence and compatibility for expected message type.
- Schema Count validation: compare expected schema versions; if mismatch, show counts and options: pick latest, pin version, or abort.
- Terraform validation: run `terraform plan` against the draft workspace (isolated workspace or plan-runner) and parse errors via terraform-validator (backend/app/services/terraform_validator.py).

5. File modification flow (conversational & repository-aware)
----------------------------------------------------------
- Edit model: all file edits are performed in the Draft Workspace (virtual FS) scoped to session.
- Discovery: assistant inspects repository to find matching modules/locals.tf files (see [project_information/mif-glue-job-creation-terraform-script-process.md](project_information/mif-glue-job-creation-terraform-script-process.md#L1) and [backend/app/graph/builder.py](backend/app/graph/builder.py#L1)).
- Proposed edits: assistant presents a diff and a short natural-language explanation (why this change) with action buttons: `Apply`, `Edit`, `Reject`.
- Edit modalities: 1) UI quick controls (dropdowns/inputs) for templated edits; 2) Inline editor for free edits.
- Versioning: every applied change is captured as a ChangeSet in session and mapped to commit messages. The user can reorder or squash commits before PR creation.

6. Kafka -> Glue Job flow (detailed)
-----------------------------------
Preconditions: user selected environment.

Step 1: Assistant derives topic name using rule: `{env}.{source_system}.{schema_grain}.raw` (e.g., `dev.saptcc.multi-1.raw`). This rule is in KB: [project_information/mif-glue-job-creation-terraform-script-process.md](project_information/mif-glue-job-creation-terraform-script-process.md#L1).

Step 2: Assistant verifies topic existence using Kafka service.
- If topic exists: proceed.
- If not: ask user whether to create topic automatically or provide alternate.

Step 3: Schema Registry validation
- Retrieve schema registry endpoint from KB for env.
- Validate that schema exists and is compatible.
- If schema count > 1: prompt user with concise options (use latest, pin specific version, show diff).

Step 4: Generate Glue job entry and Talaria args in Draft Workspace (locals.tf glue_jobs map and module glue.tf entry). Suggested default values:
- worker_type = `G.1X`
- number_of_workers = `1`
- job_type = `unified`
- cron derived automatically from natural language schedule

Step 5: Run terraform plan for the modified module and collect diagnostics.

Step 6: Present plan and allow user to accept; user may further edit Glue job code or transform chain.

7. JDBC placeholder flow
------------------------
- The assistant maps JDBC ingestion requests to the Glue job pattern with `--source=jdbc` and produces placeholders for connection strings/secret names. KB may supply hostname templates. It asks for credentials only if missing — otherwise uses user-provided secret names.

8. Flat File placeholder flow
----------------------------
- For flat-file ingestion, assistant generates S3 source patterns and Glue job configuration with `--source=flat_file`. It suggests default S3 path and checkpointing using KB patterns.

9. API placeholder flow
----------------------
- For API-driven ingestion, assistant creates a Glue job with a connector that polls the API or ingestion module and fills `--source=api`. It uses KB to populate API rate limits and auth patterns and asks for API credentials only when required.

10. Draft Workspace flow
------------------------
- Creation: on first change or explicit action, the Draft Workspace is created and associated with session ID. It is implemented as a virtual filesystem (backend/app/graph/state.py + DraftFiles service).
- Contents: staged files, Glue scripts, terraform snippets, commit metadata, validation reports.
- Editing: UI allows file open, diff view, and single-line quick edits. All edits are versioned within the session.
- Snapshotting & restore: the session persists snapshots periodically to DB; user can revert to any snapshot.
- Forking & Git mapping: when PR creation is requested, Draft Workspace diffs are converted into commits on a fork/branch via [backend/app/services/github_service.py](backend/app/services/github_service.py#L1).

11. Session restore flow
------------------------
- On UI load, if user has active sessions, show session list (with last activity timestamp). Selecting a session rehydrates the transcript, Draft Workspace, and validation state.
- Backend stores session transcript, message metadata, and DraftFiles. See [backend/app/models/session.py](backend/app/models/session.py#L1).

12. PR creation flow
---------------------
- Preconditions: GitHub OAuth token present (user opt-in). Draft Workspace validated (terraform plan pass or user accepts warnings).
- User triggers `Create PR` from assistant message or UI.
- Backend performs steps:
  1. Create fork (if necessary) and branch (naming: `copilot/{session_id}/{short-description}`).
  2. Convert ChangeSets into commits (structured messages describing Glue job edits, file modifications, validations).
  3. Push commits and create a single PR with a generated PR body that includes session transcript, validation outputs, and KB sources for defaults.
  4. Return PR URL to user.

13. User experience guidelines
-----------------------------
- Keep questions minimal and contextual; prefer dropdowns and suggested defaults.
- Show the derivation for all automated values (KB vs inference) so users can trust changes.
- Inline validations must be actionable: show quick-fix suggestions where possible.
- Always allow full edit until PR creation; edits are reversible.

14. Examples of real conversations
--------------------------------
Example 1 — Minimal user typing (Happy path):

User: "Add ingestion for `saptcc` — Kafka -> Glue; schedule hourly."

Assistant: "I will create a Glue job and Terraform entry. Environment?"

User selects `DEV`.

Assistant (automatically): "Derived topic `dev.saptcc.multi-1.raw`. Using worker defaults `G.1X`, `1` worker, Talaria `0.3.0`. Schedule `hourly` -> cron(0 * * * ? *). I added a draft entry in `locals.tf` and `glue.tf`. Run validations?" [Run Plan] [Edit]

User: [Run Plan]

Assistant: "Terraform plan OK. Topic exists in DEV. Schema registry OK. Create PR?" [Create PR]

User: [Create PR]

Assistant: "PR created: https://..." 

Example 2 — Missing KB value: scheduler ambiguity

User: "Create Glue job that runs every morning." 

Assistant: "Do you mean daily at 01:00, 06:00, or 09:00?" (presented as radio options derived from KB because 'morning' mapping ambiguous)

User selects `01:00`.

Assistant: derives cron and continues.

15. Questions that SHOULD be asked
-------------------------------
- Environment selection (DEV/PROD) — mandatory first question.
- When KB has multiple plausible values (e.g., 'morning' schedule mapping), ask a single disambiguating question with options.
- When Terraform validation fails and the fix requires privileged info (e.g., role ARN), ask specifically for that value.

16. Questions that SHOULD NOT be asked
-----------------------------------
- Low-level technical details that KB can provide (e.g., exact S3 warehouse path when KB can derive it).
- Repetitive confirmations for every derived field — avoid confirmation for each value; show derivation and ask only once at PR stage unless validation fails.

17. Auto-derivation opportunities
-------------------------------
- Topic name: `{env}.{source_system}.{schema_grain}.raw` — auto-generate.
- Cron expressions: natural-language -> cron mapping for common phrases (hourly, daily, weekly, business days, first-of-month). Use KB to map ambiguous phrases.
- Glue job name, worker defaults, job_version, target DB names and S3 warehouse prefixes using KB templates ([knowledge_base/terraform_template.json](knowledge_base/terraform_template.json#L1)).
- Kafka bootstrap endpoints, schema registry endpoints, and secret name patterns (via KB).

18. Required dropdowns and UI controls
------------------------------------
- Environment selector (DEV / PROD) — required at session start.
- Schedule selector: quick presets `Manual`, `Hourly`, `Daily`, `Weekly`, `Custom` (natural language + advanced cron editor).
- Transformer chain toggles: `Default` / `Customize` with quick toggles for `timestamp`, `kafka_unpack`, `kafka_split`.
- Topic name preview and Edit-in-place.
- Schema resolution: `Use Latest` / `Pin Version` / `Show Diff`.
- Validation actions: `Run Plan`, `Re-run validations`, `Show Logs`.

19. Agent decision matrix (high-level)
-----------------------------------
- If KB has single unambiguous value -> auto-apply and show derivation.
- If KB has multiple plausible values -> ask 1 targeted question with UI choices.
- If validation passes with warnings -> highlight warnings and allow user to proceed or fix.
- If validation fails with errors -> block PR creation until user resolves or explicitly overrides, with a required acknowledgement.

20. Fallback behavior when information is missing
-----------------------------------------------
- Provide a safe default and highlight the default clearly in UI; require user to accept before PR creation if default is security-sensitive (e.g., assume-role ARNs).
- Offer a guided quick-form that collects the missing values in a single step rather than many micro-questions.
- When external validation endpoints are unreachable (e.g., schema registry), mark validation state as `unknown` and advise user to proceed cautiously or retry.

Operational & Implementation notes (non-code)
--------------------------------------------
- LangGraph nodes: each of the following must be single-responsibility nodes wired into orchestration: `FetchKBDefaultsNode`, `LLMInterpretationNode`, `GenerateTerraformNode`, `CreateGlueJobNode`, `RunTerraformPlanNode`, `ValidateSchemaRegistryNode`, `VerifyKafkaTopicNode`, `GitHubCreatePRNode`, `DraftFilesystemNode`, `SessionPersistNode`.
- Persistence: sessions and DraftFiles persisted in DB; consider Redis for ephemeral state and queueing long-running validation tasks.
- Audit: all conversational decisions and automated derivations must be stored in `logs/audit.jsonl` with references to KB entries used.

Repository files touched (high-level)
-----------------------------------
- Backend entrypoints & services:
  - [backend/app/main.py](backend/app/main.py#L1)
  - [backend/app/config.py](backend/app/config.py#L1)
  - [backend/app/api/routes.py](backend/app/api/routes.py#L1)
  - [backend/app/api/processor.py](backend/app/api/processor.py#L1)
  - [backend/app/api/websocket.py](backend/app/api/websocket.py#L1)
  - [backend/app/services/github_service.py](backend/app/services/github_service.py#L1)
  - [backend/app/services/terraform_validator.py](backend/app/services/terraform_validator.py#L1)
  - [backend/app/services/llm_service.py](backend/app/services/llm_service.py#L1)

- LangGraph / Graph nodes:
  - [backend/app/graph/builder.py](backend/app/graph/builder.py#L1)
  - [backend/app/graph/state.py](backend/app/graph/state.py#L1)
  - [backend/app/graph/nodes/generate_terraform.py](backend/app/graph/nodes/generate_terraform.py#L1)
  - [backend/app/graph/nodes/create_pr.py](backend/app/graph/nodes/create_pr.py#L1)
  - [backend/app/graph/nodes/run_validation.py](backend/app/graph/nodes/run_validation.py#L1)

- Knowledge & templates:
  - [knowledge_base/source_systems.json](knowledge_base/source_systems.json#L1)
  - [knowledge_base/terraform_template.json](knowledge_base/terraform_template.json#L1)
  - [project_information/mif-glue-job-creation-terraform-script-process.md](project_information/mif-glue-job-creation-terraform-script-process.md#L1)

- Frontend migration to React + Vite:
  - [frontend/package.json](frontend/package.json#L1)
  - [frontend/src/app/page.tsx](frontend/src/app/page.tsx#L1)
  - [frontend/src/components/chat](frontend/src/components/chat#L1)

Deliverables from this design
----------------------------
- `docs/CONVERSATION_DESIGN.md` (this document)
- Next recommended artifacts: Session model ERD, Draft Workspace API spec, LangGraph node I/O schemas, UI wireframes for chat + draft explorer.

Next steps (pick one)
---------------------
1. Produce the detailed Session & Draft Workspace API spec (endpoints, models, error codes).
2. Produce LangGraph node I/O schemas and a sequence diagram for orchestration.
3. Produce UI wireframes and component list for React+Vite conversion.

Requested next step selection will prioritize and create a TODO entry for progress tracking.
