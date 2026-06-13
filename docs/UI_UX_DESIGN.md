# UI_UX_DESIGN — MIF Infrastructure Copilot (React + Vite)

Goal
----
Design a production-ready ChatGPT-style UI that minimizes user input and maximizes knowledge-base-driven automation. Frontend is React + Vite. Layout: left Session History, center Chat Conversation, right Draft Workspace.

Design principles
-----------------
- Non-technical users first: prefer clear labels, guided controls, defaults, and visual affordances.
- Minimize typing: use dropdowns, chips, selectors, action cards, and previews.
- Derive, show, edit: auto-derive values from KB, show derivation provenance, allow inline edit until PR creation.
- Single confirmation: only one final confirmation before PR creation.
- Session-first: sessions behave like ChatGPT with restore, rename, delete, and continue.

Global layout and responsive behavior
------------------------------------
- Layout: three-column responsive grid (Desktop):
  - Left: 280px — Session History (collapsible)
  - Center: fluid — Chat Conversation (primary focus)
  - Right: 420px — Draft Workspace (collapsible)
- Tablet: collapse Left into top-left menu; Right becomes bottom drawer.
- Mobile: single-column; session list and Draft Workspace available via drawers.

Top bar
-------
- Left: App logo + App name.
- Center: environment selector (DEV / PROD) — required and first action; current env is sticky per session.
- Right: GitHub OAuth status (avatar), New Session button, Help button.

Left Sidebar — Session History (components & interactions)
---------------------------------------------------------
Components:
- Session List (scrollable): session cards (title, timestamp, env, status badge: active/paused/draft/merged).
- Controls per session card: Continue (open), Rename (inline editable title), Delete (trash with confirmation), Duplicate (create copy), Pin.
- Actions: New Session (plus button), Filter (All / Dev / Prod / My PRs), Search (by session title or PR URL).

Behavior:
- Clicking a session opens it in center chat and loads the Draft Workspace on the right.
- Rename opens inline input; save persists immediately to backend session model.
- Delete opens confirmation modal: explain it deletes Draft Workspace snapshots; offer Export transcript option.

Center — Chat Conversation (components & interactions)
----------------------------------------------------
Components:
- Message List (in ChatGPT style): user messages (right-aligned), assistant messages (left-aligned), system messages (neutral).
- Message actions: For assistant messages that propose changes include Action Cards inline: `Apply Draft`, `Edit`, `Run Plan`, `Create PR`, `Show Diff`.
- Composer: Input bar with natural language box, quick action chips (e.g., "Create Glue Job", "Add Kafka Source", "Edit File"), voice input optional.
- Sticky validation banner: shows last validation status and quick actions.
- PR Review mini-panel: shows PR state when user is in PR flow.

Conversation patterns and UX specifics:
- Environment selection must occur before first user message; if absent, show modal with two clear big buttons `DEV` and `PROD`.
- Assistant uses Action Cards to minimize questions: propose derived values as chips (e.g., Topic: [dev.saptcc.multi-1.raw]) with small `Edit` pencil icon.
- When multiple choices exist (KB ambiguity), present a compact choice chip group rather than a free-text question.
- Avoid repeated confirmations — the assistant displays derived values inline and asks only for disambiguation when necessary.

Right Sidebar — Draft Workspace (components & interactions)
---------------------------------------------------------
Components:
- Tabs: `Files` | `Glue Jobs` | `Validations` | `Terraform Preview`
- Files tab: tree of modified files (path, change indicator, size); file open button; file diff preview inline.
- Glue Jobs tab: list of staged Glue jobs with compact cards (job name, schedule, source type, status). Each card expands to job details and quick-edit controls.
- Validations tab: list of latest validation reports (Terraform, tfsec, Schema, Kafka) with badges.
- Terraform Preview tab: rendered terraform plan summary, changed resources list, and expandable raw plan output.

Draft Workspace interactions:
- Save-to-draft: any edit in center file editor or inline action saves to draft automatically.
- Multiple file changes supported: show stack of pending ChangeSets; allow reordering, grouping into commits, and squash UI.
- Multiple Glue Jobs: allow adding, editing, and removing Glue jobs in the same draft; each job has its own card.
- Export: user can export Draft Workspace to a local zip or view PR diff before creating PR.

Repository Navigator (global component)
-------------------------------------
Place: collapsible drawer in left sidebar or accessible in top bar.
Components:
- Source System Explorer: list source systems (from `knowledge_base/source_systems.json`), each expands to folder set.
- Folder Explorer: tree view of repo folders (filter: only infra-related folders by default).
- File Explorer: list files with quick preview on hover; open to edit in Draft Workspace.
- File Preview: read-only code viewer with syntax highlighting and small header showing path and last modified commit.
- File Editor: full editor panel (monaco/codemirror) with Save-to-Draft button.

Interactions:
- Browse -> Click file -> open preview modal -> `Edit` button opens editor saving into Draft Workspace.
- Search box: fuzzy search across repo and KB.

Glue Job Creation UX — high-level
--------------------------------
Entry points:
- Chat command (e.g., "Create Glue job for saptcc from Kafka hourly")
- Action Card `Create Glue Job` in assistant messages
- Top-level `New Glue Job` button in Draft Workspace

Create flow pattern (single concise wizard inline or modal):
1. Environment (preselected)
2. Source System selector (dropdown populated from KB)
3. Ingestion Type radio: `Kafka` / `JDBC` / `Flat File` / `API`
4. Guided fields (auto-filled): Source-specific fields, schedule, workers, transformer toggles.
5. Preview Card: shows derived topic name, cron, Glue job name, terraform locals preview.
6. Validate button runs Kafka & Schema checks and Terraform plan.
7. `Add to Draft` button stages the Glue job and shows it in Draft Workspace.

Glue Job — Kafka flow (detailed)
-------------------------------
Controls & components in the wizard/modal:
- Source System dropdown (KB suggestions, search)
- Schema Grain dropdown (e.g., `multi-1`, `cdhdr`) populated from KB templates
- Topic preview chip: auto-generated as `{env}.{source_system}.{schema_grain}.raw` (editable inline)
- Schedule control: presets (`Manual`, `Hourly`, `Daily`, `Weekly`, `Custom`) + natural-language input (e.g., "every morning") with mapped options shown as radio.
- Cron preview: converted from schedule, shown in read-only with `Edit Cron` advanced control.
- Worker controls: `Worker Type` (G.1X/G.2X/G.4X) dropdown, `Number of Workers` numeric chip with stepper.
- Transformers toggles: `timestamp` and `kafka_unpack` (on/off) with default values editable.
- Secret name preview: derived pattern with `Edit` and `Use existing secret` toggle.
- Preview panel: shows a summarized Glue job card and a `Show Terraform Snippet` link.

Validation step for Kafka flow (inline):
- Topic Exists badge: green check / amber create suggestion / red not found.
- Schema Registry badge: reachable / unreachable.
- Schema Count badge: numeric, with `Show versions` link to choose latest or specific version.

JDBC, Flat File, API flows (placeholder UX)
-------------------------------------------
- All use same wizard skeleton: Source System selector -> Source-specific fields auto-filled from KB -> Preview -> Validate -> Add to Draft.
- JDBC: connection placeholder, secret selector, table pattern selector.
- Flat File: S3 path pattern suggestions, file format selector (csv/parquet/json), checkpoint path.
- API: endpoint pattern, auth type (API key/OAuth), rate-limit presets.

Auto-Derivation Engine — UI presentation and mapping
---------------------------------------------------
Purpose: show every auto-derived value, its provenance, and allow edit when needed.

Presentation pattern for derived values:
- Small chip with value + provenance icon (KB / Inference / User-provided). Hover shows tooltip: "Derived from knowledge_base/terraform_template.json: <path>".
- Edit pencil appears only for editable fields.
- Advanced toggle reveals hidden or advanced values.

Complete mapping (value -> derived / input / editable / hidden / advanced):
- Topic Name: auto-derived from `{env}.{source_system}.{schema_grain}.raw` (AUTO, editable inline, shown in preview). Provenance: `project_information` + `source_systems.json`.
- Kafka Secret Name: derived pattern (AUTO, editable, shown). Advanced: allow selecting existing secret.
- Glue Job Name / Talaria Job Name: derived from `source_system` + stream (AUTO, editable). Shown.
- IAM Role: derived if KB has mapping; otherwise required input (REQUIRES USER if missing). Shown if present; otherwise appears as red badge in validation with quick form.
- Worker Type: default `G.1X` from KB (AUTO, editable via dropdown)
- Number Of Workers: default 1 from KB (AUTO, editable)
- Schedule: user-friendly presets with NL parser (inference then user confirm). (AUTO from NL or explicit user input, editable)
- Cron Expression: derived from Schedule (AUTO, advanced editable)
- Terraform Variables / Locals / Module values: derived from KB templates (AUTO, shown in Terraform Preview; editable via advanced drawer)
- Environment Prefix: selected by user at session start (REQUIRED)
- Source System Values: from `source_systems.json` (AUTO, editable via Source System Editor)
- Schema Registry Details: from KB (AUTO, shown, editable for advanced)
- Kafka Bootstrap Servers: KB-provided per env (AUTO, hidden advanced)
- Topic Type: `.raw` or others derived per template (AUTO, editable)
- PII Flag: derived from `source_systems.json` metadata (AUTO, shown as badge; editable but flagged)
- Database Names (LH/Raw/Serving): derived from templates (AUTO, advanced editable)
- S3 paths: derived from `terraform_template.json` (AUTO, advanced editable)
- Glue Version, Retry Count, Timeout, Job Tags, Catalog Names: KB defaults (AUTO, editable under advanced)
- Validation Rules: from `validation_rules.json` (AUTO, shown in Validation tab, not editable except by admins)
- Branch Names, PR Titles, PR Descriptions, Commit messages: auto-generated using session title + short transcript (AUTO, editable before PR creation)

Which values require user input:
- Environment (first choice)
- IAM Role (if KB lacks mapping)
- Sensitive secrets (API keys or JDBC credentials) — user must provide secret name or select existing secret.
- Ambiguous schedule mappings (e.g., "morning") — user must choose from compact options.

Which values are editable:
- Almost all derived values are editable inline; advanced values are hidden behind `Advanced` toggles.

Which values are hidden by default:
- Kafka bootstrap servers, internal terraform module variables, large plan outputs, raw schema contents — available under `Advanced` or `Terraform Preview`.

Validation UX (cards, badges, details)
-----------------------------------
General presentation:
- Validations appear as small colored badges next to related entities (topic, Glue job card, file change). Clicking opens an expandable Validation Card with details, logs, and suggested fixes.

Kafka Validation cards:
- Topic Exists: check result (Exists / Not Found / Create Suggestion). Actions: `Create Topic` (if allowed) or `Use Alternate`.
- Schema Registry Reachable: endpoint ping; errors show suggestions to update KB or provide endpoint.
- Schema Count: shows number of versions and top 3 schema diffs; action buttons: `Use Latest`, `Pin Version`.

Terraform Validation cards:
- Run steps: `terraform init` -> `terraform fmt` -> `terraform validate` -> `terraform plan`.
- Card shows status icons for each step and a summarized plan delta (resources added/changed/destroyed).
- Raw plan expandable; quick-fix suggestions displayed as actionable hints.

Security Validation (tfsec):
- Run tfsec against generated plan or modules; show severity badges (Critical/High/Medium/Low) and per-issue quick-fix guidance.

Validation results UI patterns:
- Summary ribbon: green/yellow/red status.
- Small inline badges: pass/warn/fail.
- Expandable details with logs, links to KB, and recommended remediation steps.

Draft Workspace UX — details
---------------------------
Support:
- Multiple Glue Jobs: each job card editable and independently validatable.
- Multiple File Changes: file list groups by folder and allows selecting files for diff view or inline edit.
- Multiple Source Systems: allow grouping of changes per source system and per environment.

Key flows:
- Edit file -> Auto-save to Draft -> Draft list shows modified file with change count.
- Stage ChangeSet -> user optionally adds commit message -> change appears in pending commit list.
- Reorder commits -> squash -> preview final diff.

PR Review Screen
----------------
Components:
- Top summary: PR Title (editable), Target branch selector, Assignee / Reviewers UI.
- Left column: File changes (expanded diff viewer) with inline comment support.
- Middle: Glue Jobs created list with job cards and validation summaries.
- Right column: Validation Results and Terraform Summary.

Flow:
- User reviews changes, validations and derived values.
- Final checkbox: "I confirm these changes" and `Create PR` button.
- After creation: show PR link, status and CI results.

Accessibility & Keyboard UX
--------------------------
- Keyboard navigation: session list, chat messages, action cards accessible via keyboard.
- ARIA labels for all action buttons and badges.
- Colors: WCAG AA contrast for badges and text.

Component Inventory (every screen, component, modal, drawer)
----------------------------------------------------------
- Screens:
  - Home / Dashboard (session list + recent PRs)
  - Session view (chat + draft workspace)
  - PR Review screen
  - Settings / KB viewer

- Global components:
  - TopBar, EnvironmentPicker, GitHubAuthButton
  - RepositoryNavigatorDrawer

- Left Sidebar components:
  - SessionList, SessionCard, SessionFilters, SessionActionsMenu

- Center components:
  - ChatWindow, MessageBubble (User/Assistant/System), Composer, QuickActionChips
  - ActionCard: small interactive card with summary + actions (Apply/Edit/Run/PR)
  - ValidationBanner

- Right Sidebar components:
  - DraftTabs (Files/GlueJobs/Validations/Terraform)
  - FileList, FileDiffViewer, FileEditor
  - GlueJobCard, GlueJobEditor
  - ValidationCard, TerraformPlanViewer

- Modals & Drawers:
  - EnvironmentSelectModal (on new session)
  - RenameSessionModal (or inline rename)
  - DeleteSessionConfirmModal
  - NewGlueJobModal (compact wizard)
  - ValidationDetailsDrawer
  - PRCreationModal (final confirmation)

- Buttons & Controls:
  - PrimaryAction (rounded), SecondaryAction, ChipSelector, RadioGroup, Stepper (number inputs), CronEditor (advanced), FileSearch

Workflows & user interactions (detailed)
---------------------------------------
1. Start (New Session): user clicks `New Session` -> EnvironmentSelectModal -> selects `DEV` -> session created and loaded.
2. Natural request: user types "Add Kafka ingestion for saptcc hourly" -> assistant replies with ActionCard showing derived topic and preview -> user clicks `Apply Draft` -> job added to Draft Workspace.
3. Edit file: user opens `locals.tf` via repo browser -> clicks `Edit` -> editor opens -> user changes transformer -> auto-saves to Draft Workspace -> Draft Files tab updates.
4. Run validations: user clicks `Run Plan` on Terraform Preview -> validation jobs queued -> status badges update; user inspects failures and edits.
5. PR flow: user opens PR Review screen -> reviews files, glue jobs, validation -> final checkbox -> `Create PR` -> GitHub flow executes and returns PR link.

Minimizing typing & non-technical user patterns
-----------------------------------------------
- Replace free-text questions with choice chips and dropdowns where KB can propose values.
- Natural language schedule: parse to options and show a compact choice list rather than asking for cron.
- Provide contextual help icons with short one-line explanations.

State persistence & session restore
----------------------------------
- Sessions saved server-side with unique `session_id` and a Draft Workspace snapshot.
- On user login, show Recent Sessions; clicking a session rehydrates transcript and draft.

Security UX
-----------
- GitHub OAuth: show clear scopes and allow users to disconnect.
- Secrets: never show raw secret values in UI; only secret names and an indication of existence. Provide a secure flow to reference existing secrets.

Examples of production interactions (concise)
-------------------------------------------
- "Create Glue job for saptcc from Kafka hourly" -> select DEV -> assistant shows derived topic `dev.saptcc.multi-1.raw` -> user clicks `Apply Draft` -> `Run Plan` -> `Create PR`.

Next deliverables (recommended)
------------------------------
1. Low-fidelity wireframes for key screens: Session view, New Glue Job modal, Draft Workspace, PR Review.
2. Component library spec (props and events) for each component listed above.
3. API contract: session endpoints, draft FS endpoints, validation endpoints, GH endpoints.

Appendix: mapping to repository artifacts
---------------------------------------
- Knowledge base: `knowledge_base/*.json` — used to populate dropdowns and derivation provenance.
- Glue job process: `project_information/mif-glue-job-creation-terraform-script-process.md` — used to pre-fill job fields and template rules.
- LangGraph / derive_values nodes: used server-side to populate derived values shown in UI.
