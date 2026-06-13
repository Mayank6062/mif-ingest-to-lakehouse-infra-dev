# AUTO_DERIVATION_RULES — MIF Infrastructure Copilot

Purpose
-------
Define every value the Copilot can auto-derive, the knowledge sources and derivation logic, confidence levels, validation rules, fallback behaviors, and editability. Objective: minimize questions while keeping correctness.

Scope & Sources
----------------
- Files and KB consulted: `knowledge_base/source_systems.json`, `knowledge_base/terraform_template.json`, `knowledge_base/validation_rules.json`, `project_information/*`, existing `derive_values` LangGraph nodes, and Terraform generation flow in `backend/app/graph/nodes`.

Notation used in the matrix
- User Input: whether user must provide this value.
- Knowledge Source: KB file, project_information, derive_values node, or environment default.
- Derivation Logic: deterministic rule or inference path.
- Generated Value: example or pattern.
- Confidence: HIGH / MEDIUM / LOW.
- Editable: can user edit in UI before PR (Yes/No).
- Visible: shown inline (Yes), hidden by default (Hidden), or advanced (Advanced).
- Validation: automated checks to run.
- Fallback: behavior when KB data missing.

Derivation Matrix (by value)
----------------------------

1) Environment (session-level)
- User Input: Required (first step)
- Knowledge Source: User selection
- Derivation Logic: explicit user choice
- Generated Value: `DEV` or `PROD`
- Confidence: HIGH
- Editable: Yes (session settings)
- Visible: Yes
- Validation: none
- Fallback: N/A

2) Source System (e.g., `saptcc`)
- User Input: Prefer KB selection; user may type to search
- Knowledge Source: `source_systems.json`, project_information
- Derivation Logic: match user phrase to KB keys; fuzzy match if exact not found
- Generated Value: KB key string
- Confidence: HIGH if exact match, MEDIUM if fuzzy
- Editable: Yes
- Visible: Yes
- Validation: confirm existence in KB; if not found, create provisional source entry and mark PENDING
- Fallback: create provisional source with minimal defaults and flag for user confirmation

3) Schema Grain (e.g., `multi-1`, `cdhdr`)
- User Input: Optional (dropdown from KB)
- Knowledge Source: `source_systems.json` and `terraform_template.json`
- Derivation Logic: if user references a stream in free text, parse and match to KB grain list; otherwise pick default grain from KB.
- Generated Value: grain token
- Confidence: HIGH when found in KB, MEDIUM otherwise
- Editable: Yes
- Visible: Yes
- Validation: verify with Schema Registry; warn if ambiguous
- Fallback: default to `multi-1` or KB default grain

4) Topic Name (pattern: `{env}.{source_system}.{schema_grain}.raw`)
- User Input: No (auto-derived), editable inline
- Knowledge Source: `project_information` naming rules + `source_systems.json`
- Derivation Logic: format string substitution using selected env, source_system, schema_grain, topic type `.raw` from template
- Generated Value: e.g., `dev.saptcc.multi-1.raw`
- Confidence: HIGH
- Editable: Yes (inline)
- Visible: Yes
- Validation: Kafka topic existence check; name pattern validation regex
- Fallback: if any input missing, prompt minimal targeted question or mark as provisional

5) Topic Type (e.g., `.raw`)
- User Input: No (derived), editable advanced
- Knowledge Source: `project_information`, `terraform_template.json`
- Derivation Logic: per ingestion pattern use `.raw` by default for landing topics
- Generated Value: `.raw` or as KB prescribes
- Confidence: HIGH
- Editable: Advanced
- Visible: Shown with topic chip
- Validation: downstream pipeline expectations
- Fallback: default `.raw`

6) Kafka Bootstrap Servers
- User Input: No (KB-driven), require override only when missing
- Knowledge Source: `source_systems.json` keyed by env, derive_values nodes
- Derivation Logic: look up env mapping for kafka.bootstrap.servers
- Generated Value: host:port list
- Confidence: HIGH if KB entry exists, LOW if absent
- Editable: Advanced
- Visible: Hidden by default (Advanced)
- Validation: connectivity check (ping) and TLS/credential validation
- Fallback: prompt user to provide endpoint or use environment-level fallback config

7) Kafka Secret Name (and Secret Name patterns)
- User Input: Prefer select existing secret; otherwise derived
- Knowledge Source: `terraform_template.json` secret naming patterns and `source_systems.json` secrets
- Derivation Logic: apply pattern `minerva-{env}-corp-mif-{source}-gluejob-sa-cc-api-creds` or configured template
- Generated Value: e.g., `minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds`
- Confidence: MEDIUM (naming conventions stable but can vary)
- Editable: Yes
- Visible: Yes
- Validation: check secrets manager for existence by name
- Fallback: mark as missing and require user to select or create secret before PR creation

8) Glue Job Name / Job Key (logical)
- User Input: No (auto-derived), editable
- Knowledge Source: `project_information` naming rules and KB templates
- Derivation Logic: pattern `kafka-to-iceberg-batch-<source>-<stream>` with hyphenation and sanitization
- Generated Value: `kafka-to-iceberg-batch-saptce-multi-1`
- Confidence: HIGH
- Editable: Yes
- Visible: Yes
- Validation: uniqueness within folder's `glue_jobs` map; check locals.tf for duplicates
- Fallback: append incremental suffix to avoid collisions; prompt user if collision persists

9) Talaria Job Name / Job Version
- User Input: Optional
- Knowledge Source: `terraform_template.json` default `job_version` and `job_type`
- Derivation Logic: use KB default `0.3.0` unless overridden in source system metadata
- Generated Value: `0.3.0` (example)
- Confidence: HIGH
- Editable: Advanced
- Visible: Advanced
- Validation: verify compatibility with module requirements
- Fallback: default to module-supported latest stable

10) IAM Role / Assume Role ARN
- User Input: If KB lacks mapping, required
- Knowledge Source: `source_systems.json`, project_information, derive_values
- Derivation Logic: lookup per `env` mapping for sink assume-role; if missing, request user to provide ARN or select existing role
- Generated Value: `arn:aws:iam::123456789012:role/role-name`
- Confidence: MEDIUM
- Editable: Yes
- Visible: Shown when present; error badge when missing
- Validation: AWS IAM ARN format, assume-role test (if permitted)
- Fallback: mark requirement as blocking for Terraform apply; allow PR with explicit acknowledgement if user overrides (low security recommended)

11) Worker Type
- User Input: No (KB-driven default), editable
- Knowledge Source: `project_information` allowed values and defaults (G.1X/G.2X/G.4X)
- Derivation Logic: use KB default or performance profile inferred from source system (PII, throughput)
- Generated Value: `G.1X`
- Confidence: MEDIUM
- Editable: Yes
- Visible: Yes
- Validation: allowed values check
- Fallback: use `G.1X`

12) Number Of Workers
- User Input: No (KB default), editable
- Knowledge Source: `project_information` and `terraform_template.json`
- Derivation Logic: default `1`; heuristics can increase based on throughput metadata in KB
- Generated Value: `1`
- Confidence: MEDIUM
- Editable: Yes
- Visible: Yes
- Validation: integer range (1..10)
- Fallback: set to 1

13) Job Type (manual / scheduled)
- User Input: If user mentions schedule; otherwise default Manual
- Knowledge Source: `project_information` default
- Derivation Logic: parse user intent; if NL mentions schedule -> `scheduled`
- Generated Value: `manual` or `scheduled`
- Confidence: MEDIUM
- Editable: Yes
- Visible: Yes
- Validation: if scheduled, require cron expression or schedule mapping
- Fallback: Manual

14) Schedule (natural-language) and Cron Expression
- User Input: Optional NL; presets available
- Knowledge Source: NL parser + mapping table in `project_information` for ambiguous phrases
- Derivation Logic: parse NL to canonical schedule; map to cron via deterministic library; if ambiguous present quick choices
- Generated Value: Cron e.g., `cron(0 * * * ? *)`
- Confidence: MEDIUM (HIGH for standard presets)
- Editable: Cron advanced editor
- Visible: Yes (both human-friendly and cron)
- Validation: cron syntax check and Terraform module acceptance
- Fallback: ask one disambiguation question (e.g., specific hour) or default to Manual

15) Terraform Variables / Locals / Module Inputs
- User Input: Rare; mostly auto-derived
- Knowledge Source: `terraform_template.json`, derive_values node outputs, `source_systems.json`
- Derivation Logic: map job fields to module input names; apply templated substitutions and environment lookups
- Generated Value: map of module inputs, e.g., `--sink_iceberg_database`, `--sink_iceberg_warehouse`
- Confidence: HIGH for templated fields, MEDIUM for interpolated env-specific values
- Editable: Advanced (Terraform Preview drawer)
- Visible: Terraform Preview (summary) and Advanced drawer
- Validation: terraform validate / plan; tfsec for security checks
- Fallback: mark missing variables and require user to supply before PR apply or allow PR with warning depending on criticality

16) Database Names (LH/Raw/Serving)
- User Input: No (derived), editable advanced
- Knowledge Source: naming templates in `terraform_template.json` and `project_information`
- Derivation Logic: apply naming pattern `lh_<source_system_hyphenated>_raw_<env>` and sanitize
- Generated Value: e.g., `lh_sap_tcc_raw_dev`
- Confidence: HIGH
- Editable: Advanced
- Visible: Advanced
- Validation: naming conventions and DB existence checks if applicable
- Fallback: create placeholder names and mark for later edit

17) S3 Paths (warehouse, raw, landing)
- User Input: No (derived), editable advanced
- Knowledge Source: `terraform_template.json` S3 prefix templates
- Derivation Logic: format with env and source system values
- Generated Value: `s3://minerva-dev-src-dev/current/prd/raw/sap_tce/`
- Confidence: MEDIUM
- Editable: Advanced
- Visible: Advanced
- Validation: pattern checks and optionally S3 prefix existence
- Fallback: placeholder path and user prompt during PR if required

18) Iceberg / Catalog Names
- User Input: No (derived), editable
- Knowledge Source: KB templates
- Derivation Logic: map to account ids and catalog names based on env
- Generated Value: e.g., Glue Catalog id mapping
- Confidence: MEDIUM
- Editable: Advanced
- Validation: catalog access check when possible

19) PII Flag
- User Input: No (derived), editable
- Knowledge Source: `source_systems.json` metadata
- Derivation Logic: use explicit KB `pii` boolean; if absent, heuristic by dataset names or tags
- Generated Value: boolean
- Confidence: HIGH if KB explicit, LOW if heuristic
- Editable: Yes (but flagged)
- Visible: Yes (badge)
- Validation: none, but influences default retention/permissions

20) Retry Count / Timeout / Job Tags
- User Input: No (KB default), editable advanced
- Knowledge Source: `terraform_template.json`
- Derivation Logic: use module defaults; optionally use source system metadata
- Generated Value: integers / lists
- Confidence: HIGH
- Editable: Advanced
- Validation: range checks

21) Validation Rules Mapping
- User Input: No
- Knowledge Source: `validation_rules.json`
- Derivation Logic: load rule sets per job type and env
- Generated Value: list of validations executed (Kafka, Schema, TF, tfsec)
- Confidence: HIGH
- Editable: Admin-only

22) Branch Names / PR Titles / Commit Messages / PR Descriptions
- User Input: Optional (session title)
- Knowledge Source: session metadata + derived values + KB templates
- Derivation Logic: branch `copilot/{session_id}/{short-desc}`; PR title: `chore(infra): add glue job for <source_system>`; PR description includes session transcript, KB references and validation summary; commit messages per ChangeSet
- Generated Value: strings
- Confidence: MEDIUM
- Editable: Yes prior to PR creation
- Validation: GH branch name rules; PR body length checks
- Fallback: use safe generic templates

23) Schema Registry endpoint and version
- User Input: No (KB-driven), user can override
- Knowledge Source: `source_systems.json` registry mapping
- Derivation Logic: lookup per env
- Generated Value: endpoint URL and available versions list
- Confidence: HIGH if KB present, LOW otherwise
- Editable: Advanced
- Validation: endpoint reachable, version list retrieval

24) Topic Existence / Schema Count
- User Input: No (validation-only)
- Knowledge Source: live Kafka & Schema Registry queries
- Derivation Logic: call services to count schemas and topics
- Generated Value: existence boolean and integer counts
- Confidence: HIGH (live check)
- Editable: N/A
- Validation: n/a (these are validation results)

Values Identified in repo but recommended to be auto-generated in V2
------------------------------------------------------------------
- PR titles, PR descriptions, commit messages (already partially auto-generated) — recommend FULL auto-generation with editable templates.
- Cron from NL phrases — implement robust NL -> cron mapping with KB.
- Worker sizing heuristic — infer from source system throughput metadata (add to KB).
- Glue script module selection/version — infer job_version from KB module compatibility table.

Confidence levels explained
--------------------------
- HIGH: derivation uses explicit KB mapping or deterministic template (low ambiguity).
- MEDIUM: derivation uses template but depends on occasionally-missing KB entries or heuristics.
- LOW: derivation depends on heuristics, NLP inference, or external system probing that may be unreliable.

Fallback behaviors (global rules)
--------------------------------
- For HIGH-confidence derivations: apply automatically and show derivation provenance.
- For MEDIUM-confidence: auto-apply but mark as provisional and show a single inline confirmation chip allowing quick accept/change; do not prompt repeatedly.
- For LOW-confidence: present 1 targeted question (compact choices) or pre-filled form; avoid open-ended questions.
- If required sensitive values (secrets, ARNs) missing: fail validation and surface a blocking UI with steps to create/select secret. Allow PR creation only if user explicitly acknowledges risk.

Validation rules (per value)
---------------------------
- Topic name: regex /^[a-z0-9._-]+$/ and length limit; Kafka topic existence check if allowed.
- Cron: use cron parser; ensure target module accepts AWS cron format `cron(...)`.
- Secret name: check Secrets Manager API for existence when permitted.
- IAM ARN: validate ARN format and optionally IAM GetRole (if allowed).
- Worker count: 1 <= n <= 10
- Glue job name uniqueness: must not collide within `locals.tf` glue_jobs map for target folder.
- Terraform variables: run `terraform validate` and `terraform plan` and parse outputs; treat errors as blocking unless user overrides with explicit acknowledgement.

Audit & provenance
------------------
- Every derived value must be logged to `logs/audit.jsonl` with fields: `session_id`, `value_key`, `derived_value`, `source_path` (e.g., knowledge_base/terraform_template.json#Lxx), `confidence`, `timestamp`, `user_action` (if edited).

Admin & governance
-------------------
- Admins can edit KB files (`knowledge_base/*.json`) to improve derivation confidence.
- Validation rules file `validation_rules.json` controls gating behavior.

Implementation notes (non-code)
------------------------------
- Implement a Derivation Engine service that loads KB files, accepts session context, applies templated rules, and returns a derivation bundle with confidence and provenance data for UI to render.
- The LangGraph `derive_values` nodes should call the Derivation Engine; responses must include `editable`, `visibility`, `confidence`, and `provenance` fields.

Appendix: Example derivation entries (compact)
---------------------------------------------
- Topic Name: User Input: Source System + Grain + Env -> Source: KB naming rule -> Logic: format -> `dev.saptcc.multi-1.raw` -> Confidence: HIGH
- Glue Job Name: User Input: Source System -> KB pattern -> `kafka-to-iceberg-batch-saptce-multi-1` -> Confidence: HIGH
- Cron: User NL "every morning" -> KB mapping -> present options `01:00/06:00/09:00` -> Confidence MEDIUM

Next steps
----------
- Review AUTODERIVATION rules with domain experts to add any missing KB mappings.
- Implement Derivation Engine API spec and LangGraph node adapters.
- Add unit tests for each derivation with mocked KBs and sample session inputs.
