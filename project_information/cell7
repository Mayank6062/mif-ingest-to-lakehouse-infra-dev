```
Analyze all Terraform and Glue Job implementations.

Reverse engineer:

1. Topic Naming Rules
2. Source System Rules
3. Folder Creation Rules
4. locals.tf Update Logic
5. glue.tf Update Logic
6. Job Naming Rules
7. Worker Validation Rules
8. Enterprise Validation Rules
9. Subgroup Validation Rules
10. Database Naming Rules
11. S3 Warehouse Rules
12. Secret Naming Rules
13. Schema Registry Rules
14. Iceberg Rules

Create:

- Rule Catalog
- Validation Catalog
- Decision Trees
- Naming Standards

Generate markdown only.
```

# Terraform and Glue Job Reverse-Engineered Rules Catalog

## Scope

 

This document reverse engineers repository conventions from the Terraform and Glue job implementations currently present in the codebase. It focuses on naming logic, folder and file update patterns, source and topic conventions, worker sizing conventions, enterprise and subgroup usage, and Iceberg target rules.

 

This is an inferred catalog based on implementation evidence, not a formal upstream standard document.

 

---

 

## Executive Summary

 

The repository follows a convention-first implementation style.

 

The strongest recurring patterns are:

 

- one top-level folder per source system or dataset family

- one of two main Terraform entry patterns per folder:

  - `main.tf` plus `locals.tf` for external Talaria module wrappers

  - `glue.tf` plus `locals.tf` for local `modules/glue_job` orchestration

- `locals.tf` is the main business-configuration layer

- `glue.tf` is usually a thin module-wiring layer

- Kafka topics, Glue jobs, lakehouse databases, S3 warehouse paths, secrets, and schema registry references are convention-driven

- the repository mostly implements raw-layer Iceberg ingestion

 

---

 

# Part I. Rule Catalog

 

## 1. Topic Naming Rules

 

### Rule Set

 

#### TR-001: Kafka topics are usually environment-prefixed

 

Observed pattern:

 

- `${local.env}.<source>.<grain>.raw`

 

Examples of inferred shapes:

 

- `dev.wahoo.multi-1.raw`

- `dev.sfsc.multi-2.raw`

- `dev.saptcf.bseg.raw`

 

#### TR-002: Topic names usually end with `raw`

 

This is consistent with the repository’s raw-layer ingestion focus.

 

#### TR-003: Topic middle segments usually encode source system plus schema grain or business object

 

Common grain patterns include:

 

- `multi-1`

- `multi-2`

- named business objects such as `bseg`, `cdhdr`, `acdoca`, `i_supplier`

 

#### TR-004: Topic names are often mirrored into Iceberg table derivation logic

 

The shared Glue module strips or normalizes punctuation and removes `raw` or `clean` state suffixes when deriving table prefixes.

 

### Reverse-Engineered Standard

 

Preferred standard:

 

`<environment>.<source_system>.<schema_grain_or_object>.raw`

 

### Risk Notes

 

- changing topic segment order would likely break implicit table derivation

- omitting `raw` would likely make the topic inconsistent with existing naming logic

 

---

 

## 2. Source System Rules

 

### Rule Set

 

#### SR-001: One top-level folder usually represents one source system or tightly related dataset family

 

#### SR-002: Folder name usually becomes the default source-system identity

 

This is reinforced by CI-injected locals where `source_system = basename(path.root)`.

 

#### SR-003: Source-system identity is reused across multiple artifacts

 

Typical reuse points:

 

- folder name

- topic naming

- secret naming

- sink database naming

- warehouse naming

- Glue workflow naming in JDBC patterns

 

#### SR-004: External module pattern may explicitly set `source_system`

 

External Talaria-module folders frequently pass `source_system = local.source_system` or a literal source-system value.

 

### Reverse-Engineered Standard

 

A valid source-system identifier should be:

 

- stable across environments

- reused across topics, jobs, secrets, and sinks

- short enough to embed in job and path names

- consistent with folder naming

 

---

 

## 3. Folder Creation Rules

 

### Rule Set

 

#### FR-001: Every deployable top-level folder must be included in `.vela.py`

 

This is enforced by repository validation.

 

#### FR-002: New folders should match one of the recognized deployment patterns

 

Primary patterns:

 

- `locals.tf` plus `main.tf` external-module pattern

- `locals.tf` plus `glue.tf` local-module pattern

- specialized pattern for edge cases such as ECS or testing

 

#### FR-003: `locals.tf` is expected in source folders

 

It commonly defines:

 

- `ent_func`

- `subgroup`

- source-specific maps or job definitions

- environment mapping locals for endpoints or account IDs

 

#### FR-004: Folder naming should align with source-system naming

 

The folder name is not just cosmetic; it becomes part of CI and source identity logic.

 

### Reverse-Engineered Standard

 

A valid new folder should:

 

- sit at repository top level

- map to one deployment boundary

- be added to `.vela.py`

- inherit one of the recognized file layouts

- include ownership locals

 

---

 

## 4. `locals.tf` Update Logic

 

### Rule Set

 

#### LR-001: `locals.tf` is the main place for source-specific business configuration

 

#### LR-002: For local-module folders, `locals.tf` usually holds `glue_jobs`

 

Each `glue_jobs` entry usually contains:

 

- job name key

- job type

- job version

- optional worker settings

- optional schedule

- source and sink argument maps

 

#### LR-003: `locals.tf` also often stores environment maps

 

Common maps include:

 

- Kafka bootstrap endpoints by environment

- schema registry endpoints by environment

- target account IDs by environment

 

#### LR-004: `locals.tf` must define ownership attributes

 

Common fields:

 

- `ent_func`

- `subgroup`

 

#### LR-005: `locals.tf` often carries the most important source-to-sink contract information

 

Examples:

 

- topic name

- secret name

- sink database

- warehouse path

- assume-role ARN

- checkpoint path

 

### Reverse-Engineered Update Logic

 

When adding a new job or topic, update `locals.tf` first if the folder already uses the local shared module pattern.

 

---

 

## 5. `glue.tf` Update Logic

 

### Rule Set

 

#### GR-001: `glue.tf` is typically thin wiring, not deep business configuration

 

#### GR-002: In local-module folders, `glue.tf` usually iterates over `local.glue_jobs`

 

Typical responsibilities:

 

- set `for_each = local.glue_jobs`

- pass through optional values using `lookup`

- map source job configuration to shared-module inputs

 

#### GR-003: `glue.tf` may expose defaults through `lookup`

 

Common defaults observed:

 

- `glue_version = 5.0`

- `number_of_workers = 2`

- `worker_type = G.1X`

- `job_type = kafka_to_iceberg`

 

#### GR-004: `glue.tf` should not duplicate large configuration maps already held in `locals.tf`

 

### Reverse-Engineered Update Logic

 

Update `glue.tf` only when:

 

- the folder’s module-wiring shape must change

- a new optional argument must be passed through

- worker settings or stop-before-start flags are not yet wired

- the folder is being created for the first time

 

If only a new topic or job is being added to an already-wired folder, prefer updating `locals.tf` only.

 

---

 

## 6. Job Naming Rules

 

### Rule Set

 

#### JR-001: Shared-module job names are environment-prefixed

 

The shared module builds:

 

- `${var.env}-${var.name}`

 

This means the source folder usually provides the semantic job name, and the module adds the environment prefix.

 

#### JR-002: Local job keys often embed source, sink style, and grain

 

Examples of inferred shapes:

 

- `kafka-to-iceberg-wahoo-multi-1`

- `kafka-to-iceberg-concur-core-user`

 

#### JR-003: JDBC ingest job names follow an explicit pattern

 

Observed shape:

 

- `ingest_<source>_<target_or_source_table>_<full_or_delta>_<env>`

 

#### JR-004: JDBC export job names follow an explicit pattern

 

Observed shape:

 

- `export_<target_name>_<target_table_name>_full_<env>`

 

### Reverse-Engineered Standard

 

| Pattern | Standard |

| --- | --- |

| Shared Glue module | `<env>-<semantic_job_name>` |

| JDBC ingest | `ingest_<source>_<table>_<mode>_<env>` |

| JDBC export | `export_<target>_<table>_full_<env>` |

 

---

 

## 7. Worker Validation Rules

 

### Rule Set

 

#### WR-001: Default worker count for shared Glue jobs is usually `2`

 

#### WR-002: Default worker type for shared Glue jobs is usually `G.1X`

 

#### WR-003: Explicit overrides are used for heavier topics or tables

 

Observed worker types:

 

- `G.025X`

- `G.1X`

- `G.2X`

- `G.4X`

 

#### WR-004: Larger workers are associated with heavier or partitioned jobs

 

Common signals that larger workers are justified:

 

- heavy SAP or finance datasets

- larger partition counts

- known high-volume sources

- JDBC extraction with large source tables

 

#### WR-005: Worker settings belong in `locals.tf` data where folder pattern supports overrides

 

### Reverse-Engineered Standard

 

| Workload Class | Likely Worker Convention |

| --- | --- |

| lightweight or frequent Kafka topic | `G.025X` or `G.1X` |

| default shared ingestion | `G.1X` with 2 workers |

| moderate-heavy structured workloads | `G.2X` |

| heavy partitioned JDBC extraction | `G.4X` |

 

### Caution

 

The repository does not contain a strict numeric validation rule beyond supported AWS worker strings. The practical rule is convention-based: start from the nearest comparable workload.

 

---

 

## 8. Enterprise Validation Rules

 

### Rule Set

 

#### ER-001: Each source folder should declare `ent_func`

 

Observed values include:

 

- `AGTR`

- `CORP`

- `FOOD`

- `SPEC`

 

#### ER-002: `ent_func` is used as ownership metadata, not just documentation

 

It feeds into common tagging via CI-injected locals.

 

#### ER-003: `ent_func` should align with target sink naming and business ownership where possible

 

### Reverse-Engineered Valid Set

 

Likely accepted set in current repository practice:

 

- `AGTR`

- `CORP`

- `FOOD`

- `SPEC`

 

### Validation Meaning

 

If a new folder introduces a new `ent_func`, it should be treated as a governance-level change and reviewed carefully.

 

---

 

## 9. Subgroup Validation Rules

 

### Rule Set

 

#### SGR-001: Each source folder should declare `subgroup`

 

Observed values include:

 

- `AGTR_APAC`

- `ANH`

- `APAC`

- `CBI`

- `CORP_DTD`

- `CORP_FIN`

- `DTD`

- `FIN`

- `FSGL`

- `GTC`

- `HR`

- `TDA`

- `TDA_COCOA`

- `WTG`

 

#### SGR-002: `subgroup` contributes to tagging and ownership context

 

#### SGR-003: `subgroup` values are less normalized than `ent_func`

 

The repository contains multiple subgroup naming styles, including abbreviations and compound forms.

 

### Reverse-Engineered Validation Rule

 

A valid subgroup should:

 

- map to an existing business ownership pattern where possible

- remain stable within a source family

- be treated as a governance field, not an arbitrary free-text label

 

---

 

## 10. Database Naming Rules

 

### Rule Set

 

#### DBR-001: Most targets are raw-layer databases

 

#### DBR-002: Two major naming families are present

 

Family A:

 

- `minerva_<env>_src_<domain>_<source>_prd_raw_db`

 

Family B:

 

- `lh_<source>_raw_<env>`

- `lh_<source>_report_raw_<env>`

 

#### DBR-003: Environment is encoded in the database name

 

#### DBR-004: Raw state is encoded in the database name

 

### Reverse-Engineered Standard

 

Preferred forms:

 

- `minerva_<env>_src_<business_domain>_<source_system>_prd_raw_db`

- `lh_<source_system>_raw_<env>`

 

### Risk Notes

 

- mixing naming families inside one source family should be treated as exceptional

- non-raw database suffixes are not supported by strong repository evidence

 

---

 

## 11. S3 Warehouse Rules

 

### Rule Set

 

#### SWR-001: Warehouse paths are almost always raw-layer paths

 

#### SWR-002: Warehouse paths usually encode environment, domain grouping, and source

 

Observed families include:

 

- `s3://minerva-<env>-src-<domain>/current/prd/raw/<source>/`

- `s3://dev-lh1-<domain>-src/raw/current/<env_or_prd>/src/<source>/`

 

#### SWR-003: Warehouse path and database naming usually move together

 

#### SWR-004: Source-system identity should appear in the terminal warehouse path segment

 

### Reverse-Engineered Standard

 

A warehouse path should usually:

 

- point to the raw layer

- end with the source system path component

- be environment-correct

- be consistent with the source family already used in that folder

 

---

 

## 12. Secret Naming Rules

 

### Rule Set

 

#### SER-001: Kafka credential secrets often follow a stable pattern

 

Observed pattern:

 

- `minerva-${local.env}-corp-mif-<source>-gluejob-sa-cc-api-creds`

 

#### SER-002: JDBC secrets often use source-based secret names managed in `jdbc_batch`

 

Examples suggest source-centric naming such as:

 

- `minerva-dev-ingest-<source>-prod`

- similar source-system based secret patterns

 

#### SER-003: Secret names are usually environment-aware and source-aware

 

#### SER-004: The same secret may be reused for both source Kafka access and sink transformer operations

 

### Reverse-Engineered Standard

 

For Kafka-oriented jobs, prefer:

 

- `minerva-<env>-corp-mif-<source_system>-gluejob-sa-cc-api-creds`

 

For JDBC-oriented flows, prefer the existing subsystem-specific source secret pattern instead of inventing a new one.

 

---

 

## 13. Schema Registry Rules

 

### Rule Set

 

#### SRR-001: Schema registry endpoints are commonly defined as environment maps in `locals.tf`

 

#### SRR-002: Schema registry is mainly used where Kafka unpacking and sink split behavior are configured

 

#### SRR-003: Source folders usually reference schema registry via:

 

- `local.schema_registry_endpoint[local.env]`

 

#### SRR-004: Schema registry secret names often align with the Kafka secret naming pattern

 

### Reverse-Engineered Standard

 

If a folder uses Kafka unpack plus split-to-Iceberg behavior, it should usually define:

 

- schema registry endpoint map by environment

- matching secret reference for the sink split transform

 

---

 

## 14. Iceberg Rules

 

### Rule Set

 

#### IR-001: Iceberg is the default lakehouse sink convention

 

Evidence:

 

- datalake format set to `iceberg`

- sink arguments consistently reference Iceberg database, warehouse, checkpoint, and catalog settings

 

#### IR-002: Raw-layer jobs write to Iceberg-backed raw schemas and warehouse paths

 

#### IR-003: Iceberg checkpoints use environment-aware S3 buckets

 

Common shape:

 

- `s3://minerva-<env>-glue-checkpoints/checkpoints/<mode>/`

 

#### IR-004: Shared-module non-unified jobs may auto-derive `iceberg_table_prefix`

 

This is based on normalized topic naming.

 

#### IR-005: Cross-account writes are common

 

Many jobs specify:

 

- Iceberg catalog ID

- assume-role ARN

- assume-session name

 

### Reverse-Engineered Standard

 

A complete Iceberg sink contract usually includes:

 

- target database

- target warehouse path

- checkpoint directory

- catalog type and catalog ID

- assume-role ARN

- assume-session name

 

---

 

# Part II. Validation Catalog

 

## A. Structural Validation Catalog

 

| ID | Validation Rule | Severity |

| --- | --- | --- |

| VC-001 | New top-level folder must be included in `.vela.py` | Critical |

| VC-002 | `.vela.yml` must be regenerated from `.vela.py` after pipeline changes | Critical |

| VC-003 | Source folders should contain `locals.tf` and a recognized Terraform entry file | High |

| VC-004 | New implementation should match one existing repository pattern unless clearly exceptional | High |

 

## B. Topic and Job Validation Catalog

 

| ID | Validation Rule | Severity |

| --- | --- | --- |

| VC-101 | Kafka topics should be environment-prefixed and usually end with `.raw` | High |

| VC-102 | Topic grain should be source-specific and stable | Medium |

| VC-103 | Shared-module job names should remain compatible with `<env>-<semantic_name>` logic | High |

| VC-104 | JDBC job names should keep the `ingest_` or `export_` naming contract | High |

 

## C. Ownership Validation Catalog

 

| ID | Validation Rule | Severity |

| --- | --- | --- |

| VC-201 | Each source folder should define `ent_func` | High |

| VC-202 | Each source folder should define `subgroup` | High |

| VC-203 | New `ent_func` values should be treated as governance exceptions | Medium |

| VC-204 | `subgroup` values should be consistent within a source family | Medium |

 

## D. Sink and Iceberg Validation Catalog

 

| ID | Validation Rule | Severity |

| --- | --- | --- |

| VC-301 | Database name should encode environment and raw-layer intent | High |

| VC-302 | Warehouse path should encode raw-layer storage and source identity | High |

| VC-303 | Secret name should encode environment and source identity | High |

| VC-304 | Schema registry reference should be environment-aware when used | High |

| VC-305 | Iceberg sink contract should include database, warehouse, and checkpoint intent | High |

 

## E. Worker Validation Catalog

 

| ID | Validation Rule | Severity |

| --- | --- | --- |

| VC-401 | Worker type should be one of observed supported conventions: `G.025X`, `G.1X`, `G.2X`, `G.4X` | Medium |

| VC-402 | Default worker assumptions should remain 2 workers and `G.1X` unless workload justifies override | Medium |

| VC-403 | Heavy partitioned jobs should justify larger worker classes | Medium |

 

---

 

# Part III. Decision Trees

 

## 1. Folder Creation Decision Tree

 

Need a new implementation?

→ Does an existing source folder already represent the source system?

→ Yes

→ Reuse the existing folder

→ Update `locals.tf` first

 

Need a new implementation?

→ Does an existing source folder already represent the source system?

→ No

→ Create a new top-level folder

→ Add `locals.tf`

→ Choose folder pattern

→ Register folder in `.vela.py`

→ Regenerate `.vela.yml`

 

## 2. `locals.tf` vs `glue.tf` Decision Tree

 

Need to add a new topic or job?

→ Does the folder already have a `glue_jobs` map in `locals.tf`?

→ Yes

→ Add the new job entry in `locals.tf`

→ Only change `glue.tf` if the wiring lacks a needed passthrough

 

Need to add a new topic or job?

→ Does the folder use external Talaria modules in `main.tf`?

→ Yes

→ Add a new module block or update module arguments in `main.tf`

→ Keep business constants in `locals.tf`

 

## 3. Shared Module Change Decision Tree

 

Need new behavior?

→ Can the change be represented by existing job arguments in one folder?

→ Yes

→ Keep change local to source folder

 

Need new behavior?

→ Can the change be represented by existing job arguments in one folder?

→ No

→ Does more than one folder need the behavior?

→ Yes

→ Consider updating `modules/glue_job`

→ Treat as high-blast-radius change

 

## 4. Worker Selection Decision Tree

 

New job requires worker sizing

→ Is it similar to existing light Kafka ingestion?

→ Yes

→ Start from `G.1X` and 2 workers, or `G.025X` if matching local precedent

 

New job requires worker sizing

→ Is it a heavier structured dataset or repeated large-volume source?

→ Yes

→ Compare with nearby `G.2X` implementations

 

New job requires worker sizing

→ Is it a large partitioned JDBC load?

→ Yes

→ Compare with nearby `G.4X` implementations

 

## 5. Naming Family Decision Tree

 

Need a sink database and warehouse

→ Does the source family already use `minerva_<env>_src_..._raw_db` naming?

→ Yes

→ Reuse that family

 

Need a sink database and warehouse

→ Does the source family already use `lh_<source>_raw_<env>` naming?

→ Yes

→ Reuse that family

 

Need a sink database and warehouse

→ No family exists yet

→ Pick one family and keep database and warehouse paths consistent together

 

---

 

# Part IV. Naming Standards

 

## Topic Naming Standard

 

Preferred format:

 

`<environment>.<source_system>.<schema_grain_or_object>.raw`

 

## Source Folder Naming Standard

 

Preferred format:

 

`<source_system>`

 

Where needed, retain existing hyphenated family naming for grouped source domains.

 

## Shared Glue Job Naming Standard

 

Preferred format after module expansion:

 

`<environment>-<semantic_job_name>`

 

Semantic job name should usually encode:

 

- ingestion style

- source system

- grain or business object

 

## JDBC Ingest Job Naming Standard

 

Preferred format:

 

`ingest_<source_system>_<table_name>_<full_or_delta>_<environment>`

 

## JDBC Export Job Naming Standard

 

Preferred format:

 

`export_<target_name>_<target_table_name>_full_<environment>`

 

## Database Naming Standard

 

Preferred formats:

 

- `minerva_<env>_src_<domain>_<source>_prd_raw_db`

- `lh_<source>_raw_<env>`

- `lh_<source>_report_raw_<env>`

 

Use the same family already present in the source domain.

 

## Warehouse Naming Standard

 

Preferred characteristics:

 

- S3 path

- raw-layer indicator present

- source identity in terminal path segment

- environment-correct bucket family

 

## Secret Naming Standard

 

Kafka-oriented preferred format:

 

`minerva-<env>-corp-mif-<source_system>-gluejob-sa-cc-api-creds`

 

JDBC-oriented preferred format:

 

- follow the existing `jdbc_batch` source secret family for that subsystem

 

## Schema Registry Standard

 

Preferred format:

 

- define `schema_registry_endpoint` as an environment map in `locals.tf`

- reference it as `local.schema_registry_endpoint[local.env]`

 

## Ownership Naming Standard

 

Preferred folder-local fields:

 

- `ent_func = <enterprise_code>`

- `subgroup = <subgroup_code>`

 

Prefer existing values where possible instead of inventing new labels.

 

---

 

## Final Interpretation

 

The repository is built around stable conventions rather than centrally enforced complex schemas. The strongest reverse-engineered rules are:

 

- keep new work inside an existing folder when possible

- use `locals.tf` for source-specific business configuration

- use `glue.tf` as a thin module-wiring layer

- preserve topic, database, warehouse, secret, and schema registry naming families already established in the source domain

- treat changes to shared modules, CI files, or JDBC core logic as high-blast-radius platform changes

 

The safest implementation strategy is imitation of the nearest valid precedent, not invention of a new local pattern