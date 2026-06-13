```
Analyze this repository and identify automation opportunities.

Document:

1. Potential AI Agents
2. Agent Objectives
3. Inputs
4. Outputs
5. Business Value

Create:

- Agent Development Knowledge Base
- Validation Rules Catalog
- Monitoring Rules Catalog
- Agent Roadmap

Generate markdown only.
```
# Repository Automation Opportunities
 
## Executive Summary
 
This repository is a strong candidate for AI-assisted automation because it is:
 
- highly configuration-driven
- repetitive across many source folders
- sensitive to naming and convention drift
- operationally dependent on runtime signals from AWS Glue, CloudWatch, EventBridge, SNS, and Datadog
- reliant on review-intensive Terraform changes with uneven blast radius
 
The highest-value automation opportunities are not generic coding assistants. They are repository-aware agents that understand:
 
- folder-scoped Terraform deployment
- raw lakehouse ingestion patterns
- shared module blast radius
- JDBC workflow sequencing
- source-to-sink configuration contracts
- operational health and failure triage
 
---
 
## 1. Potential AI Agents
 
### Agent Portfolio Overview
 
| Agent | Primary Objective | Core Inputs | Core Outputs | Business Value |
| --- | --- | --- | --- | --- |
| Source Onboarding Agent | Generate new source-folder scaffolding and baseline configuration | source type, domain, target lakehouse pattern, schedule, secrets, connectivity requirements | proposed folder structure, locals map, module selection guidance, readiness checklist | reduces onboarding time and standardizes new ingestion patterns |
| Terraform Change Review Agent | Analyze pull requests for risk, correctness, and convention compliance | changed Terraform files, shared module changes, pipeline changes, naming patterns | change summary, risk score, impacted folders, review comments, validation checklist | improves review quality and reduces missed side effects |
| Change Impact Agent | Detect deployment and runtime blast radius before merge | git diff, module dependencies, folder-to-pipeline mappings, runtime conventions | impact report, affected folders, impacted AWS behaviors, recommended validation depth | lowers outage risk from shared changes |
| Lakehouse Naming Agent | Validate database, warehouse, topic, and table naming consistency | sink database names, S3 warehouse paths, topic names, schema grain, environment names | naming violations, normalized recommendations, drift report | prevents schema fragmentation and data discoverability issues |
| Configuration Consistency Agent | Detect config drift across similar source folders and job maps | locals files, glue job maps, shared defaults, secret naming, schedules | consistency findings, duplicate patterns, recommended consolidation candidates | reduces maintenance cost and hidden divergence |
| Schema Contract Agent | Check schema-facing inputs and infer contract risks | schema registry endpoints, topic names, table prefixes, flat-file data model references | schema readiness report, missing contract flags, evolution risk summary | reduces ingestion failures caused by schema mismatches |
| JDBC Workflow Agent | Analyze table sequencing, extraction strategy, and workflow correctness | jdbc_batch source configs, source tables, delta fields, partition settings, triggers | workflow graph, sequencing risks, parallelization opportunities, notification coverage report | improves reliability and efficiency of JDBC pipelines |
| Operational Triage Agent | Diagnose failed or unhealthy jobs using repository context and runtime signals | job names, CloudWatch patterns, EventBridge state, health-check output, recent deployments | probable cause analysis, affected scope, recovery steps, escalation hints | reduces time to resolution during incidents |
| Restart Decision Agent | Recommend whether a job should be restarted, left running, or escalated | active runs, runtime duration, job history, recent deployment status, failure pattern | restart recommendation, safety notes, incident action summary | avoids unsafe restarts and improves operator judgment |
| Test Coverage Agent | Recommend validation strategy for changed components | diff scope, folder type, shared module usage, test stacks, runtime risk class | suggested test plan, representative folders to validate, runtime checks | improves confidence before apply |
| Monitoring Coverage Agent | Detect gaps in alerts, health checks, and observability | job patterns, notification resources, health-check scope, logging arguments | missing-monitoring report, alert coverage gaps, observability action plan | reduces blind spots in production-like operations |
| Runbook Assistant Agent | Produce and maintain operational runbooks from repository truth | deployment patterns, runtime behaviors, scripts, health-check logic, notifications | runbook drafts, troubleshooting trees, operator checklists | keeps operational documentation current |
 
---
 
## 2. Agent Objectives
 
### A. Source Onboarding Agent
 
**Objective**
 
Accelerate creation of new ingestion stacks while preserving repository conventions.
 
**Repository Fit**
 
This repository contains many source folders with repeated patterns. New source onboarding is a strong automation target because the work is structured, repetitive, and convention-heavy.
 
### B. Terraform Change Review Agent
 
**Objective**
 
Act as a repository-specialized reviewer for Terraform and CI changes.
 
**Repository Fit**
 
The repository has many similar folders plus a few high-risk shared components. Human review is expensive because reviewers must mentally map local changes to shared runtime behavior.
 
### C. Change Impact Agent
 
**Objective**
 
Estimate blast radius and downstream operational risk before deployment.
 
**Repository Fit**
 
Changes to `modules/glue_job`, `.vela.py`, `.vela.yml`, `.ci/common-files`, and `jdbc_batch` can impact many deployments at once.
 
### D. Lakehouse Naming Agent
 
**Objective**
 
Enforce consistent raw-layer naming and sink conventions.
 
**Repository Fit**
 
The repository depends heavily on naming conventions for discoverability and correctness, especially in database names, warehouse paths, and topic-to-table derivation.
 
### E. Configuration Consistency Agent
 
**Objective**
 
Find inconsistent defaults, duplicated logic, and near-identical job definitions that should be standardized.
 
**Repository Fit**
 
Large `locals.tf` maps and repeated source-folder patterns create natural drift over time.
 
### F. Schema Contract Agent
 
**Objective**
 
Reduce runtime failures caused by missing or inconsistent schema assumptions.
 
**Repository Fit**
 
Schema behavior is distributed across topic names, schema registry endpoints, Talaria arguments, and optional flat-file data model artifacts.
 
### G. JDBC Workflow Agent
 
**Objective**
 
Improve correctness and efficiency of JDBC workflows.
 
**Repository Fit**
 
The `jdbc_batch` subsystem behaves like a sub-platform with workflow ordering, partitioning, delta logic, notifications, and health-check dependencies.
 
### H. Operational Triage Agent
 
**Objective**
 
Turn repository context plus runtime signals into faster incident diagnosis.
 
**Repository Fit**
 
Troubleshooting currently requires joining data from deployment history, job configuration, logs, health checks, and notification signals.
 
### I. Restart Decision Agent
 
**Objective**
 
Help operators decide whether restart is safe and useful.
 
**Repository Fit**
 
The repository already supports controlled restart behavior, but the decision logic remains manual.
 
### J. Test Coverage Agent
 
**Objective**
 
Recommend the right validation depth for each change.
 
**Repository Fit**
 
The repository has infrastructure checks and test stacks, but no obvious automated decision layer that maps changes to the right validation strategy.
 
### K. Monitoring Coverage Agent
 
**Objective**
 
Identify jobs and workflows that lack sufficient alerting or health coverage.
 
**Repository Fit**
 
Observability is layered, but coverage differs across standard Glue jobs, JDBC workflows, and specialized tasks.
 
### L. Runbook Assistant Agent
 
**Objective**
 
Continuously transform repository truth into operator guidance.
 
**Repository Fit**
 
Runbooks are derivable from infrastructure definitions, scripts, and health rules, making them suitable for semi-automated generation.
 
---
 
## 3. Inputs
 
### Common Repository Inputs
 
Most agents should share a common input foundation:
 
- source folder Terraform files
- shared module files
- CI/CD definitions
- job naming conventions
- topic names and schema grain values
- sink database and warehouse paths
- secret names and connection names
- restart and health-check scripts
- test-stack definitions
- architecture documentation
 
### Runtime and Operational Inputs
 
Operational agents additionally need:
 
- Glue job states
- CloudWatch log excerpts
- EventBridge failure events
- SNS notification mappings
- Datadog health payloads
- recent deployment history
- job-run recency and duration signals
 
### Agent-Specific Inputs
 
| Agent | Important Inputs |
| --- | --- |
| Source Onboarding Agent | source type, source system, domain, schedule, expected sink, credentials model |
| Terraform Change Review Agent | pull request diff, dependency map, changed folders, changed shared components |
| Change Impact Agent | diff scope, module usage graph, pipeline path rules, folder classification |
| Lakehouse Naming Agent | topic names, lakehouse database names, warehouse paths, table prefixes |
| Configuration Consistency Agent | all `locals.tf`, `glue.tf`, `main.tf`, module arguments, shared defaults |
| Schema Contract Agent | schema registry endpoints, topic names, data model paths, sink transform settings |
| JDBC Workflow Agent | `jdbc_batch` source definitions, table maps, partition settings, delta fields, schedules |
| Operational Triage Agent | job state, error logs, health-check output, recent change history |
| Restart Decision Agent | running job metadata, elapsed duration, last success, restart scripts, deployment timestamp |
| Test Coverage Agent | change type, impacted files, folder type, shared module usage, test stack availability |
| Monitoring Coverage Agent | notification resources, health-check scope, log settings, metrics settings |
| Runbook Assistant Agent | scripts, architecture docs, monitoring patterns, failure signals |
 
---
 
## 4. Outputs
 
### Common Output Types
 
The best outputs for this repository are structured and operationally actionable.
 
Typical outputs:
 
- markdown reports
- risk scores
- validation checklists
- folder impact maps
- recommended tests
- naming violation reports
- probable cause summaries
- runbook drafts
- workflow diagrams in text form
- prioritized remediation items
 
### Output Expectations by Agent
 
| Agent | Expected Outputs |
| --- | --- |
| Source Onboarding Agent | onboarding design, folder template recommendation, required inputs checklist, deployment readiness summary |
| Terraform Change Review Agent | PR summary, high-risk findings, missing validations, convention drift notes |
| Change Impact Agent | blast radius matrix, affected folders, runtime risk classification, rollout advice |
| Lakehouse Naming Agent | naming conformance score, violation list, normalized name suggestions |
| Configuration Consistency Agent | duplication report, outlier configurations, consolidation candidates |
| Schema Contract Agent | schema dependency map, missing contract warnings, evolution-risk notes |
| JDBC Workflow Agent | workflow sequence map, fragile chain points, partitioning or delta tuning suggestions |
| Operational Triage Agent | likely root cause, impacted scope, next actions, escalation threshold |
| Restart Decision Agent | restart or do-not-restart recommendation, risk note, preconditions checklist |
| Test Coverage Agent | recommended validation plan, representative folders to test, post-deploy checks |
| Monitoring Coverage Agent | alert-gap inventory, missing health signals, observability backlog |
| Runbook Assistant Agent | generated runbooks, troubleshooting steps, incident decision trees |
 
---
 
## 5. Business Value
 
### Value Themes
 
The automation opportunities map to five business-value themes:
 
- faster onboarding of new data sources
- lower change failure rate
- lower operational toil
- better governance and consistency
- faster incident response
 
### Business Value by Agent
 
| Agent | Business Value |
| --- | --- |
| Source Onboarding Agent | reduces lead time for new ingestion sources |
| Terraform Change Review Agent | improves review quality and reduces configuration defects |
| Change Impact Agent | lowers risk of broad failures from shared changes |
| Lakehouse Naming Agent | improves data platform consistency and discoverability |
| Configuration Consistency Agent | reduces maintenance cost and accidental divergence |
| Schema Contract Agent | lowers ingestion breakage from schema mismatches |
| JDBC Workflow Agent | improves reliability and efficiency of table-based workflows |
| Operational Triage Agent | reduces mean time to diagnose failures |
| Restart Decision Agent | reduces unsafe operational actions |
| Test Coverage Agent | increases confidence while focusing validation effort |
| Monitoring Coverage Agent | reduces undetected operational failures |
| Runbook Assistant Agent | preserves institutional knowledge and improves operator readiness |
 
---
 
# Agent Development Knowledge Base
 
## Repository Facts an Agent Must Know
 
### 1. Repository Shape
 
This repository is not a monolithic Terraform root. It is a collection of many folder-scoped Terraform deployment units.
 
### 2. Primary Runtime Model
 
The main runtime target is AWS Glue, with secondary support for ECS-based Talaria tasks and JDBC workflow chains.
 
### 3. Primary Data Platform Role
 
The repository mainly implements raw-layer ingestion into Iceberg-backed lakehouse targets.
 
### 4. Primary Shared Components
 
The most important shared components are:
 
- `modules/glue_job`
- `.vela.py`
- `.vela.yml`
- `.ci/common-files`
- `jdbc_batch/modules`
- `jdbc_batch/health_check`
- `scripts/restart_job.sh`
 
### 5. High-Risk Change Zones
 
Agents should treat these paths as high risk:
 
- `modules/glue_job/**`
- `.vela.py`
- `.vela.yml`
- `.ci/common-files/**`
- `jdbc_batch/locals.tf`
- `jdbc_batch/modules/**`
- `jdbc_batch/secrets.tf`
- `scripts/restart_job.sh`
- `jdbc_batch/health_check/**`
 
### 6. Folder Patterns an Agent Should Recognize
 
Agents should classify folders into at least four patterns:
 
- external Talaria module wrappers
- local shared Glue module stacks
- JDBC subsystem assets
- specialized task or test folders
 
### 7. Naming Knowledge
 
Agents should understand the following conventions:
 
- source topics frequently include `.raw`
- sink databases commonly include `_raw_db` or `lh_<source>_raw_<env>`
- warehouse paths commonly include `/raw/`
- job names encode source, grain, mode, and environment
 
### 8. Operational Signal Knowledge
 
Agents should understand these operational signals:
 
- Glue states such as `SUCCEEDED`, `FAILED`, `TIMEOUT`, and `STOPPED`
- EventBridge-based failure routing
- SNS-based notifications in the JDBC subsystem
- CloudWatch as the main log sink
- Datadog as a summarized health destination for JDBC monitoring
 
### 9. Testing Knowledge
 
Agents should know that validation in this repository is mostly:
 
- static CI checks
- Terraform plan review
- targeted integration stacks
- runtime observation after deployment
 
### 10. Scope Boundaries
 
Agents should not assume this repository contains:
 
- full downstream silver or gold transformations
- all executable Talaria logic locally
- complete schema contracts inside Terraform alone
 
---
 
# Validation Rules Catalog
 
## Rule Categories
 
### A. Structural Rules
 
| Rule ID | Rule | Why It Matters |
| --- | --- | --- |
| VR-001 | Every deployable folder should match a recognized implementation pattern | prevents orphaned or inconsistent stack layouts |
| VR-002 | Shared pipeline definitions should remain render-consistent between source and rendered forms | prevents CI/CD drift |
| VR-003 | Source folders should contain only configuration relevant to their deployment boundary | limits hidden blast radius |
| VR-004 | Shared module changes should trigger high-risk review classification | reflects multi-folder blast radius |
 
### B. Naming Rules
 
| Rule ID | Rule | Why It Matters |
| --- | --- | --- |
| VR-101 | Raw ingestion sinks should use raw-consistent naming in database and warehouse targets | preserves lakehouse consistency |
| VR-102 | Topic, grain, and table-prefix relationships should be internally coherent | prevents broken topic-to-table derivation |
| VR-103 | Environment naming should align across folder, database, warehouse, and secret usage | reduces cross-environment mistakes |
| VR-104 | Source-system identifiers should remain stable across job name, secret name, and sink location | improves traceability |
 
### C. Configuration Rules
 
| Rule ID | Rule | Why It Matters |
| --- | --- | --- |
| VR-201 | Required source arguments should exist for the selected job type | avoids runtime misconfiguration |
| VR-202 | Required sink arguments should exist for the selected sink type | avoids failed writes |
| VR-203 | Secret names should match expected environment and source conventions | reduces credential lookup failures |
| VR-204 | Schedules should be explicit and reviewable for recurring jobs | prevents silent scheduling drift |
| VR-205 | Worker size and concurrency should match expected workload class | reduces runaway cost or underprovisioning |
| VR-206 | Checkpoint and warehouse paths should align to the chosen environment | reduces cross-environment contamination |
 
### D. JDBC Rules
 
| Rule ID | Rule | Why It Matters |
| --- | --- | --- |
| VR-301 | JDBC workflows should have a valid first trigger and coherent next-step chaining | preserves workflow integrity |
| VR-302 | Delta jobs should declare valid delta fields and safety behavior | prevents missing or duplicate ingestion |
| VR-303 | Partition settings should be present and sensible for large tables | improves performance and stability |
| VR-304 | Notification configuration should exist for operationally critical workflows | reduces undetected failures |
| VR-305 | Source and target naming should remain coherent across workflow resources | improves troubleshooting |
 
### E. Operations Rules
 
| Rule ID | Rule | Why It Matters |
| --- | --- | --- |
| VR-401 | Jobs with operational restart behavior should explicitly declare the intended semantics | prevents unsafe automatic restarts |
| VR-402 | Logging arguments should be present for long-running jobs | preserves diagnosability |
| VR-403 | Monitoring coverage should exist for critical workflows | reduces operational blind spots |
| VR-404 | High-risk shared changes should require representative validation, not only syntax checks | improves release safety |
 
---
 
# Monitoring Rules Catalog
 
## Coverage Principles
 
Monitoring rules should focus on execution health, freshness, failure visibility, and operational completeness.
 
### A. Glue Runtime Rules
 
| Rule ID | Rule | Signal | Response Goal |
| --- | --- | --- | --- |
| MR-001 | Detect job terminal failure | Glue state = `FAILED` | trigger rapid triage |
| MR-002 | Detect timeout events | Glue state = `TIMEOUT` | investigate source slowness or sizing issues |
| MR-003 | Detect repeated stop-start patterns | frequent `STOPPED` then restarted | identify unstable operations or bad deployment loops |
| MR-004 | Detect excessive run duration | runtime exceeds expected schedule window | determine whether job is stuck or source is degraded |
 
### B. Freshness Rules
 
| Rule ID | Rule | Signal | Response Goal |
| --- | --- | --- | --- |
| MR-101 | Detect stale scheduled jobs | last success beyond allowed threshold | protect downstream freshness |
| MR-102 | Detect missing first-run success after deployment | deployment succeeded but expected run never completed | catch silent release issues |
| MR-103 | Detect workflow chain gaps | first JDBC step runs but downstream steps do not continue | identify broken conditional triggers |
 
### C. Data Movement Rules
 
| Rule ID | Rule | Signal | Response Goal |
| --- | --- | --- | --- |
| MR-201 | Detect source-target count mismatch | count difference exceeds tolerance | catch data quality or write issues |
| MR-202 | Detect zero-source or zero-target anomalies where unexpected | observed count pattern is abnormal | catch broken extraction or write paths |
| MR-203 | Detect repeated delta jobs with no effective movement when not expected | repeated low-change pattern | identify source-side or delta-config issues |
 
### D. Observability Rules
 
| Rule ID | Rule | Signal | Response Goal |
| --- | --- | --- | --- |
| MR-301 | Detect jobs missing log signals | no recent CloudWatch activity for active or scheduled jobs | identify observability gaps |
| MR-302 | Detect jobs lacking error-routing resources in JDBC patterns | missing EventBridge or SNS configuration | close alerting blind spots |
| MR-303 | Detect health-check scope gaps | operationally critical JDBC jobs absent from health interpretation workflows | expand monitoring coverage |
 
### E. Change-Aware Rules
 
| Rule ID | Rule | Signal | Response Goal |
| --- | --- | --- | --- |
| MR-401 | Detect post-shared-module anomaly spike | failures increase after shared component deploy | prioritize rollback or hotfix investigation |
| MR-402 | Detect post-pipeline-change deployment regressions | unusual plan/apply failures after CI/CD edits | isolate pipeline-level defects |
| MR-403 | Detect post-source-change sink divergence | one source folder shows new warehouse or schema anomalies after deployment | identify local configuration drift |
 
---
 
# Agent Roadmap
 
## Phase 1: Quick-Win Agents
 
### Priority
 
Build agents that operate on repository files and pull requests first.
 
### Recommended Agents
 
1. Terraform Change Review Agent
2. Change Impact Agent
3. Lakehouse Naming Agent
4. Test Coverage Agent
 
### Why First
 
- low operational risk
- high review-time value
- no need for deep runtime integration to start
- immediate benefit in pull request workflows
 
### Expected Outcomes
 
- faster reviews
- improved consistency
- better pre-merge risk awareness
 
## Phase 2: Configuration and Platform Governance Agents
 
### Recommended Agents
 
1. Configuration Consistency Agent
2. Schema Contract Agent
3. Monitoring Coverage Agent
4. Runbook Assistant Agent
 
### Why Second
 
- these agents require more repository-specific knowledge
- they improve medium-term maintainability and governance
- they convert hidden conventions into explicit control mechanisms
 
### Expected Outcomes
 
- reduced configuration drift
- clearer schema assumptions
- more complete monitoring coverage
- better operator documentation
 
## Phase 3: Operational Intelligence Agents
 
### Recommended Agents
 
1. Operational Triage Agent
2. Restart Decision Agent
3. JDBC Workflow Agent
 
### Why Third
 
- these agents depend on runtime integrations and stronger signal quality
- they benefit from the validation catalogs and knowledge base built in earlier phases
- they provide the strongest incident-management value once grounded in real operational telemetry
 
### Expected Outcomes
 
- lower mean time to diagnose
- safer incident handling
- better understanding of JDBC workflow fragility
 
## Phase 4: End-to-End Source Automation
 
### Recommended Agents
 
1. Source Onboarding Agent
2. Composite Platform Copilot that combines review, impact, validation, and operational guidance
 
### Why Fourth
 
- end-to-end automation should only follow after rules, naming, risk classification, and monitoring logic are mature
- onboarding quality depends on having accurate repository patterns and validation rules already encoded
 
### Expected Outcomes
 
- faster source onboarding
- standardized stack creation
- reduced expert dependency for repetitive infrastructure design
 
---
 
## Recommended First Implementation Set
 
If only three agents are built first, the recommended set is:
 
1. Terraform Change Review Agent
2. Change Impact Agent
3. Operational Triage Agent
 
This combination covers:
 
- prevention before merge
- blast-radius awareness before deployment
- faster diagnosis after failures
 
---
 
## Final Recommendation
 
This repository is especially well suited for AI agents that reason over structured infrastructure conventions and operational metadata. The best opportunities are not generic generation tasks. They are repository-aware control, review, validation, and triage agents that reduce human cognitive load across three moments:
 
- before change
- during deployment
- after runtime failure
 
The strongest initial value will come from agents that make hidden repository knowledge explicit, enforce validation rules, and connect configuration changes to operational risk.