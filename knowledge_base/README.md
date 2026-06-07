# Glue Job Creation Agent — Knowledge Base

## Overview

This knowledge base contains everything needed to build and run the **Glue Job Creation Agent** for the `mif-ingest-to-lakehouse-infra-dev` repository.

The agent helps engineers create new AWS Glue job Terraform entries for Kafka → Lakehouse (Iceberg) data pipelines — without needing direct access to the source repository.

---

## Knowledge Base Files

| File | Purpose |
|---|---|
| [validation_rules.json](validation_rules.json) | All business and technical validation rules (topic, jobs, workers, enterprise, sink, S3, secrets, Iceberg) |
| [terraform_template.json](terraform_template.json) | Exact Terraform entry structure with field descriptions, defaults, and derivation logic |
| [source_systems.json](source_systems.json) | Known source system folders, pattern types, and new system creation checklist |
| [agent_system_prompt.md](agent_system_prompt.md) | Complete system prompt for the agent: roles, questioning strategy, validation, output format, guardrails |
| [decision_trees.md](decision_trees.md) | Mermaid flowcharts, state machine, auto-derivation rules, sample conversations |

---

## Quick Reference: Key Rules

### Topic Pattern
```
{env}.{source_system}.{schema_grain}.raw
```
Examples: `dev.saptcc.multi-1.raw`, `dev.wahoo.cdhdr.raw`

### Job Name Auto-Derivation
```
kafka-to-iceberg-batch-{source_system}-{schema_grain}
```
Example: `kafka-to-iceberg-batch-saptcc-multi-1`

### Worker Types
`G.025X` | `G.1X` (default) | `G.2X` | `G.4X` — max 10 workers

### Enterprise (ent_func)
`AGTR` (default) | `CORP` | `FOOD` | `SPEC`

### Terraform Job Type
`unified` (default) | `unified_batch` | `kafka_to_iceberg` | `kafka_to_iceberg_batch`

### Source System Logic
- **Folder exists** → Update `{source_system}/locals.tf` only
- **New folder** → Create `locals.tf` + `glue.tf` + register in `.vela.py`

---

## What the Agent Can Do

1. Accept a Kafka topic name and derive all possible values automatically
2. Ask targeted follow-up questions for the 4 sink values that cannot be derived
3. Validate every input against the rules in `validation_rules.json`
4. Detect whether the source system is new or existing
5. Generate the complete `locals.tf` Terraform entry
6. Generate the file creation checklist for new source systems
7. Output a PR-ready checklist

---

## Data Sources for This Knowledge Base

| Source | Content Used |
|---|---|
| `project_information/cell1` | Repository overview, business flow, architecture, source system list |
| `project_information/cell2` | Component inventory, locals.tf + glue.tf patterns, module types |
| `project_information/cell3` | Lakehouse layers, schema patterns, configuration |
| `project_information/cell4` | Vela CI/CD, deployment process, .vela.py requirements |
| `project_information/cell5` | Agent opportunity analysis |
| `project_information/cell6` | Onboarding SOPs, PR process, new folder creation steps |
| `project_information/cell7` | Full rule catalog: TR/SR/FR/LR/JR/WR/ER/SGR/DBR/SWR/SER/SRR/IR rules |
| `project_information/cell8` | Mermaid diagrams, JSON schemas, sample conversations |
| `project_information/mif-glue-job-creation-terraform-script-process.md` | **Ground truth**: Exact Terraform template, all parameters, validation rules |

---

## Next Steps (Phase 3 — Agent Build)

```
agent/
├── glue_job_agent.py       ← Main conversational agent logic
├── validator.py            ← Rule engine (loads validation_rules.json)
├── terraform_generator.py  ← Template filler (loads terraform_template.json)
└── knowledge_loader.py     ← Loads and indexes all knowledge base files
```

Run with:
```bash
python agent/glue_job_agent.py
```

Demo flow:
```
User: Create a Glue job for dev.saptcc.multi-1.raw
Agent: [Validates → Derives values → Collects sink params → Confirms → Generates Terraform]
```
