**Repository Navigator Specification**

Purpose
-------
- **Goal:** Provide a production-ready, implementation-facing specification for a repository navigator that enables discovery, guided editing, and session-driven Draft Workspace operations for the MIF Infrastructure Copilot. The navigator centers on the Draft Workspace as the single source-of-truth for session edits and supports iterative Glue Job creation and multi-file edits culminating in a single validation and a single PR.

Principles
----------
- **Draft-First:** The Draft Workspace collects all changes (new files, edits, deletions) during the session. No direct writes to main branches without a PR.
- **Never Ask:** The UI/agent must never ask questions that can be derived from KB or repository state — specifically it must never ask "How many Glue Jobs do you want to create?" or similarly non-actionable quantity prompts.
- **Iterative:** Users perform repeated operations (Create Glue Job, Modify Files); after each operation the agent asks exactly: "What would you like to do next?" with the standard option list.
- **Context Preservation:** Environment, derived values, and Draft changes persist across the session and can be restored later.
- **Intelligent Discovery:** Selecting a file triggers automated discovery of related Terraform files, Glue Jobs, variables, secrets, modules, and validation rules.

Key Terms
---------
- **Environment:** The target deployment context (e.g., `dev`, `staging`, `prod`) plus credentials and selected GitHub repo/branch context.
- **Operation:** One user action: `Modify Existing Files` or `Create Glue Job`.
- **Draft Workspace:** In-memory + persisted session layer storing a set of `DraftFile` artifacts and metadata. The canonical working copy for the session.
- **DraftFile:** A single file change record (path, originalHash, content, changeType, metadata).
- **DerivationEntry:** A derived value record with provenance and confidence (see `AUTO_DERIVATION_RULES`).
- **ValidationReport:** Result of running validators (terraform validate/plan, tfsec, custom rules).

Navigation State Model
----------------------
The navigator maintains a compact state object that maps directly to UI and backend session storage. Fields below are descriptive; implementers should convert to their chosen persistence format.

- **NavigatorState**
  - `sessionId` (string) — unique session identifier
  - `environment` (object) — environment id & metadata
  - `gitContext` (object) — repo, baseBranch, forkBranch, commitSha (optional)
  - `cursor` (object)
    - `sourceSystem` (string|null)
    - `folderPath` (string|null)
    - `subfolderPath` (string|null)
    - `selectedFilePath` (string|null)
    - `previewMode` (enum: code|rendered|hcl|md)
  - `draftWorkspaceId` (string) — pointer to Draft Workspace
  - `lastOperation` (object)
    - `type` (enum: create_glue_job, modify_file, review_draft, validate, create_pr)
    - `timestamp` (ISO)
    - `summary` (string)
  - `derivedValues` (DerivationEntry[])
  - `relatedIndex` (map[filePath -> RelatedFilesSummary])

- **DraftWorkspace**
  - `id` (string)
  - `authorSession` (sessionId)
  - `files` (DraftFile[])
  - `glueJobs` (GlueJobSummary[])
  - `createdAt` / `updatedAt`
  - `validation` (ValidationReport|null)
  - `status` (enum: open|validated|ready_for_pr|merged|abandoned)

- **DraftFile**
  - `path` (string)
  - `changeType` (enum: add|modify|delete)
  - `originalHash` (string|null)
  - `content` (string)
  - `editable` (boolean)
  - `derivedFrom` (DerivationEntry[])

User Flows
----------
Flow A — Browse & Edit (Modify Existing Files)
- 1. Environment selected or resumed.
- 2. User navigates: Source System → Folder → Subfolder → File (navigator updates `cursor`).
- 3. System renders a Preview (code or rendered view). It also discovers related files (see Related File Discovery Flows).
- 4. User clicks Edit → editor opens with draft layer overlay.
- 5. User saves: edits are persisted as a `DraftFile` into `DraftWorkspace` (create if absent).
- 6. Agent responds: "Saved to draft workspace. What would you like to do next?" (Options list presented).

Flow B — Create Glue Job (No quantity prompts)
- 1. Environment selected.
- 2. User chooses `Create Glue Job` operation.
- 3. Agent collects required property values by deriving from KB + repository: names, prefixes, default locations. Only ask clarifying questions when values cannot be derived or when multiple unambiguous choices exist.
- 4. Agent scaffolds Glue Job artifacts in Draft Workspace (Terraform modules, job definitions, IAM policy snippets) as `DraftFile` entries.
- 5. Agent confirms: "Created Glue Job draft: <name>. Saved to draft workspace. What would you like to do next?"

Flow C — Iteration & Repeat
- After any operation, present the same next-step options: Create Another Glue Job, Modify Existing Files, Review Draft Workspace, Create Pull Request.
- Selecting Create Another Glue Job repeats Flow B without resetting the Draft Workspace.

AI Decision Flows
-----------------
- **Derive-first:** For every required property, run the Derivation Engine with repository + KB context. If `confidence >= threshold` (configurable), use derived value silently and record `DerivationEntry` with provenance.
- **Clarify-only-when-necessary:** Only prompt the user when a required property cannot be derived or when multiple high-confidence alternatives exist. Prompts must be single-value and context-rich — never freeform quantity questions.
- **Auto-linking:** Upon file selection or draft creation, run related-file discovery (heuristics below) and attach `RelatedFilesSummary` to the `NavigatorState`.

Related File Discovery Flows
---------------------------
When a file is selected or created the navigator runs these discovery steps (ordered and stop-when-enough):
- 1. **Path neighbors:** Search sibling files and same-folder Terraform files (`*.tf`, `*.tf.json`).
- 2. **Name matching:** Find files with matching prefixes/suffixes (e.g., `<job_name>_job.tf`, `glue_*`, `job_*`).
- 3. **Module references:** Parse Terraform `module` blocks in nearby `*.tf` files to locate used modules.
- 4. **Variable usage:** Identify `variable` declarations and `locals` referenced by the file.
- 5. **Secrets references:** Detect secrets/secret names (vault, secrets manager) via patterns and service references.
- 6. **Glue manifests:** Detect existing Glue job definitions in `glue` folders or `jobs` manifests.
- 7. **Validation rules:** Match files to validation rules in `knowledge_base/validation_rules.json` and register impacts in `RelatedFilesSummary`.

For each related file return `RelatedFilesSummary`:
- `filePath`, `relationType` (sibling|module|variable|secret|validation), `confidence`, `notes`

Draft Workspace Flows
---------------------
- **Save semantics:** Saving a file writes into the Draft Workspace as a `DraftFile`. Original repository remains untouched.
- **Preview & Diff:** Users can review Draft Workspace with side-by-side diffs to any base branch.
- **Merging duplicates:** If multiple operations edit the same file in the Draft, record as a single `DraftFile` with the last edit winning; keep a `changeHistory` array for audit.
- **Glue Job creation:** Glue Job drafts produce both job-specific files and any referenced terraform module edits as linked `DraftFile` entries.

Validation & PR Flow
--------------------
- **Single Validation Gate:** The user initiates `Validate Draft` which runs configured validators once across the entire Draft Workspace (terraform init/plan, tfsec, custom checks). The ValidationReport is attached to DraftWorkspace.
- **Validation Impact Flow:** Validators produce actionable findings; each finding maps to DraftFile(s) and is displayed with quick-fix suggestions. The agent may propose fixes (as additional DraftFiles) which the user can accept.
- **Create PR:** On `Create Pull Request`, the system packages the DraftWorkspace into a single branch/commit, attaches the ValidationReport and derivation provenance, and opens a PR. After merge, DraftWorkspace status moves to `merged`.

Session Restore Flows
---------------------
- **Checkpointing:** Persist `NavigatorState` and `DraftWorkspace` to durable storage keyed by `sessionId` and `userId` after each operation.
- **Resume:** On user return, load the latest `NavigatorState` and `DraftWorkspace`. Restore UI cursor and rehydrate derived values and relatedIndex.
- **Conflict detection:** If repository state changed while the session was idle (e.g., remote branch advanced), surface `rebaseRequired` and provide guided rebase/resync operations in the UI rather than forcing decisions.

Error Flows
-----------
- **Save conflicts:** If saving a DraftFile collides with another draft change, present a 3-way merge view and allow the user to accept theirs, accept incoming, or merge manually.
- **Derivation failures:** If the Derivation Engine times out or returns low confidence, ask a single targeted question describing the missing value and why it is needed.
- **Validation failures:** Surface failing validators grouped by severity. For fatal errors (block PR), require explicit user acceptance of suggested fixes before PR creation.

Validation Impact & Governance
------------------------------
- All validation runs must be recorded with a `ValidationReport` and attached to the PR.
- The agent must produce an audit trail: which derivations were used, by which LangGraph node, and the user approvals for any auto-applied changes.

User Experience Rules (Hard Constraints)
--------------------------------------
- Always present the single follow-up question: "What would you like to do next?" with these options:
  - Create Another Glue Job
  - Modify Existing Files
  - Review Draft Workspace
  - Create Pull Request
- Never ask quantity prompts that can be derived from KB or repository (e.g., "How many Glue Jobs?").
- Avoid repeated confirmations; prefer one explicit confirmation at PR creation.

Implementation Notes for Engineers (non-code)
-------------------------------------------
- Persist `NavigatorState` and `DraftWorkspace` using a session-backed store (Postgres + JSONB recommended). Keep `DraftFile` contents in object storage if large.
- DerivationEntry schema must include `value`, `confidence`, `provenance` (KB file + rule id + source path), `timestamp`.
- Index `relatedIndex` lazily and cache per session to reduce repeated scans.
- Provide server-side APIs: listFolders(sourceSystem), listFiles(folder), previewFile(path, mode), openEditor(filePath, draftWorkspaceId), saveDraftFile(draftFile), listDraftFiles(draftWorkspaceId), validateDraft(draftWorkspaceId), createPR(draftWorkspaceId).

Appendix: Example Flow — Create Glue Job (compact)
-------------------------------------------------
1. User: selects environment `dev` → clicks `Create Glue Job`.
2. Agent: derives jobName, glueRole, terraformModulePath from KB + repo.
3. Agent: creates files in Draft Workspace (`glue/<jobName>/main.tf`, `glue/<jobName>/job.json`, `modules/glue-job/variables.tf`).
4. Agent: responds "Created glue job draft `<jobName>`. Saved to draft workspace. What would you like to do next?"

Document History
----------------
- v1.0 — Production-ready spec created (includes state model, user flows, discovery flows, validation & session restore requirements).

See also
--------
- Conversation design: [docs/CONVERSATION_DESIGN.md](docs/CONVERSATION_DESIGN.md)
- UI/UX design: [docs/UI_UX_DESIGN.md](docs/UI_UX_DESIGN.md)
- Auto derivation rules: [docs/AUTO_DERIVATION_RULES.md](docs/AUTO_DERIVATION_RULES.md)
- State model: [docs/STATE_MODEL_V2.md](docs/STATE_MODEL_V2.md)
