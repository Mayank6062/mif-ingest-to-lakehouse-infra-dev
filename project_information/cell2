```
Analyze this repository and document:

1. Class Inventory
   - Classes
   - Responsibilities
   - Dependencies

2. Method Inventory
   - Inputs
   - Outputs
   - Failure Conditions

3. Execution Flow
   - Startup
   - Processing
   - Shutdown

4. Kafka Analysis
   - Topics
   - Producers
   - Consumers
   - Message Structure

5. Data Flow Analysis
   - Source
   - Transformations
   - Destination

Generate structured markdown.

Do not generate code.
```


# Repository Architecture Analysis

 

## Purpose

 

This repository is an Infrastructure-as-Code estate for the development environment of the Minerva ingestion platform. Its primary role is to define, deploy, and operate AWS-based ingestion pipelines that move data from many upstream enterprise systems into lakehouse storage.

 

The repository is organized around source-specific Terraform stacks. Each source folder represents a deployable unit, and the delivery pipeline applies Terraform only for folders that changed.

 

## Architectural Summary

 

At a high level, the repository implements a hub-and-spoke architecture:

 

- The repository root provides delivery, governance, and shared module capabilities.

- Source folders act as spokes, each defining one ingestion domain or dataset family.

- Shared Terraform modules standardize Glue job creation, scheduling, permissions, and registry updates.

- A dedicated `jdbc_batch` area supports higher-volume and more customized JDBC ingestion and export workflows.

- CI/CD automation orchestrates per-folder plan and apply operations, plus operational monitoring and restart workflows.

 

## Major Components

 

### 1. Source Stack Layer

 

The majority of the repository consists of source-specific folders such as AGTR, SAP, Aurora, Concur, OpenMeteo, and others.

 

These folders follow three main implementation patterns:

 

#### A. External Talaria staging-to-Iceberg stacks

Used by folders such as AGTR variants, `food-pros`, `genetec`, `customer-hierarchy`, and similar domains.

 

Characteristics:

 

- Small Terraform footprint, usually `locals.tf` plus `main.tf`

- Depend on an external shared module from `minerva-talaria-terraform-modules`

- Focus on declaring source identity, Talaria version, scanner strategy, target lakehouse database, target bucket, and IAM role names

- Best suited for standardized ingestion scenarios where the platform module already encapsulates most behavior

 

Primary responsibility:

 

- Declare a source-to-lakehouse ingestion endpoint with minimal local customization

 

#### B. Internal Glue job map stacks

Used by folders such as `concur`, `aurora`, `axapta`, `iiq`, `m3`, `fts`, `saptc1`, `saptc2`, `sfsc`, `wahoo`, and many others.

 

Characteristics:

 

- Typically contain `locals.tf` and `glue.tf`

- Store a large local map of Glue jobs and job arguments

- Reuse the repository-local `modules/glue_job` module

- Support Kafka, batch, streaming, flat-file, and unified ingestion modes

- Centralize repeated job creation through `for_each`

 

Primary responsibility:

 

- Define multiple ingestion jobs for a source domain while reusing a standardized local module for Glue orchestration

 

#### C. Specialized ingestion and utility stacks

Used by folders such as `leapsf`, `talariatst-tsv`, and `talariatst`.

 

Characteristics:

 

- Mix standard modules with specialized ones such as Salesforce-to-staging and ECS-based Talaria task execution

- Used for experimental, test, or non-standard ingestion entry points

 

Primary responsibility:

 

- Support edge cases, trial patterns, or source-specific ingestion approaches that do not fit the main two patterns

 

### 2. Shared Glue Job Module

 

The `modules/glue_job` module is the repository’s main reusable orchestration primitive for non-JDBC source folders.

 

It provides:

 

- AWS Glue job creation

- Default argument assembly for Talaria-based jobs

- Script and library resolution from artifact storage

- Optional IAM role creation or reuse of existing roles

- Trigger scheduling support

- Network connection selection for VPC access

- DynamoDB registry item creation for retry metadata

- Optional data model publication to S3 for flat-file scenarios

- Automatic Lambda invocation to restart or start jobs after job definition changes

 

Primary responsibility:

 

- Convert declarative source/job configuration into runnable AWS Glue workloads with consistent operational behavior

 

### 3. JDBC Batch Platform

 

The `jdbc_batch` folder is effectively a sub-platform inside the repository.

 

It supports large-scale JDBC ingestion and selected export workflows through a more customized architecture than the generic Glue module.

 

Core elements include:

 

- Source-level Terraform definitions for many JDBC systems

- Reusable internal modules for source orchestration, source tables, target orchestration, target tables, and notification subscriptions

- Shared local settings for roles, buckets, scripts, drivers, and Glue connections

- Secrets registration and import management

- Glue workflows for chaining jobs across many tables in sequence

- SNS and EventBridge-based failure notification patterns

- Health-check automation that evaluates job freshness and data movement quality

 

Primary responsibility:

 

- Manage complex, table-oriented JDBC ingestion and export jobs that require sequential workflows, per-table scheduling behavior, and richer operational controls

 

### 4. CI/CD and Runtime Injection Layer

 

The repository uses Vela for delivery orchestration.

 

Key elements:

 

- `.vela.py` is the canonical pipeline definition source

- `.vela.yml` is the rendered operational pipeline file

- `.ci/common-files` contains Terraform provider, variable, and default local definitions copied into source folders at runtime

- The pipeline runs linting, folder validation, Terraform plan, Terraform apply, restart automation, scheduled health checks, and delivery monitoring

 

Primary responsibility:

 

- Ensure each source folder can be deployed independently while sharing consistent runtime Terraform context and governance controls

 

### 5. Operational Automation Layer

 

This layer includes:

 

- `scripts/restart_job.sh` for controlled job stop/start operations

- `jdbc_batch/health_check` for periodic health assessment and Datadog reporting

- Monitoring pipeline steps that report Vela execution outcomes

 

Primary responsibility:

 

- Provide day-2 operations support beyond infrastructure provisioning

 

### 6. Governance and Repository Metadata

 

This layer includes:

 

- `CODEOWNERS`

- Pre-commit configuration

- Terraform documentation configuration

- Existing repository documentation files

 

Primary responsibility:

 

- Enforce ownership, consistency, and repository hygiene

 

## Responsibilities by Component

 

| Component | Primary Responsibilities |

| --- | --- |

| Source stack folders | Declare source-specific ingestion intent, target lakehouse destination, source-level schedules, and source-specific settings |

| `modules/glue_job` | Standardize Glue job creation, common arguments, network access, optional IAM, scheduling, registry updates, and restart behavior |

| `jdbc_batch` source definitions | Describe JDBC sources, source tables, extraction logic, schedules, and job chaining |

| `jdbc_batch` internal modules | Build workflows, notifications, per-table jobs, and exports |

| `.ci/common-files` | Inject shared provider, variable, and environment logic during CI runtime |

| `.vela.py` and `.vela.yml` | Orchestrate lint, plan, apply, health checks, restart steps, and monitoring |

| `scripts` and `health_check` | Support operations, restart flows, and observability |

| External Talaria modules | Encapsulate platform-standard ingestion patterns such as staging-to-Iceberg, Salesforce-to-staging, and ECS-based tasks |

 

## Dependency Model

 

### Core Platform Dependencies

 

#### AWS Services

 

The repository depends heavily on AWS managed services:

 

- AWS Glue for ingestion job execution

- Amazon S3 for artifacts, checkpoints, staging, and lakehouse storage

- AWS IAM for execution and cross-account access

- AWS Secrets Manager for source credentials and API secrets

- Amazon EventBridge and AWS Glue triggers for scheduling and orchestration

- Amazon CloudWatch for execution events and logs

- Amazon SNS for operational notifications

- AWS Lambda for job start or restart automation

- Amazon DynamoDB for Talaria retry registry state

- AWS ECS for selected specialized Talaria task executions

 

#### External Module Dependencies

 

The repository relies on external Terraform modules hosted in the Minerva Git server, especially:

 

- Staging-to-Iceberg ingestion modules

- Salesforce-to-staging modules

- ECS Talaria task modules

 

These external modules encapsulate platform conventions and reduce local repository complexity for standardized patterns.

 

#### Talaria Runtime Dependencies

 

The ingestion jobs depend on Talaria job artifacts and supporting Python libraries stored in artifact S3 locations.

 

Dependency categories include:

 

- Talaria runtime packages

- Schema handling packages

- Serialization and validation libraries

- JDBC drivers for source connectivity

 

#### External Data-System Dependencies

 

The runtime jobs depend on upstream systems outside the repository, including:

 

- JDBC-accessible enterprise databases

- Kafka topics and brokers

- Schema registry endpoints

- Flat-file or staged file locations

- Downstream lakehouse accounts and assume-role targets

 

## Internal Dependencies

 

### Folder-to-CI dependency

 

Every source stack depends on CI runtime injection of common Terraform files unless it overrides them locally.

 

### Source-to-module dependency

 

Most source folders are very thin wrappers over either:

 

- the external Talaria Terraform modules, or

- the local `modules/glue_job` module

 

This means business intent is decentralized, but implementation behavior is centralized.

 

### JDBC source-to-submodule dependency

 

The `jdbc_batch` area depends on nested modules for:

 

- source orchestration

- source-table job generation

- export orchestration

- export-table job generation

- notification subscription setup

 

## Interaction Model

 

### 1. Repository change to deployment

 

1. A change is made in a source folder.

2. Vela detects the changed path.

3. CI injects common Terraform files into the folder.

4. Terraform plan runs for pull requests.

5. Terraform apply runs on pushes to main.

6. Resulting infrastructure changes update or create the source’s AWS resources.

 

This design makes the folder the main deployment boundary.

 

### 2. Source stack to AWS runtime

 

For standard source folders:

 

1. A source folder declares source identity and ingestion settings.

2. The folder invokes either an external platform module or the local Glue module.

3. The module creates Glue jobs, triggers, and related metadata.

4. The Glue job retrieves scripts and libraries from artifact storage.

5. The runtime connects to Kafka, JDBC, or staged files.

6. Data is transformed and written to Iceberg-backed lakehouse storage.

 

### 3. Internal Glue module operational flow

 

The local Glue module performs several cross-cutting interactions:

 

- Resolves the script and dependency package locations from artifact storage

- Selects one or more Glue VPC connections for network-enabled jobs

- Merges default job arguments with source-specific arguments

- Reuses or creates IAM roles

- Registers retry metadata in DynamoDB

- Optionally creates a schedule trigger

- Optionally invokes a Lambda function to start the Glue job after a job update

 

This makes the module both a provisioning component and an operational bootstrap component.

 

### 4. JDBC batch orchestration flow

 

The JDBC batch path uses a more explicit workflow model:

 

1. A source definition provides connection settings, source metadata, schedules, and table definitions.

2. The source module creates an SNS topic and EventBridge rule for failure notifications.

3. The source module creates a Glue workflow for that source.

4. The source module expands the table list into many Glue jobs.

5. The first table job is scheduled directly.

6. Subsequent jobs are triggered conditionally after the previous job succeeds.

7. Each Glue job extracts source data and writes to the lakehouse target.

 

This pattern is optimized for multi-table JDBC ingestion where sequence control matters.

 

### 5. Monitoring and health interactions

 

Operational monitoring occurs through multiple channels:

 

- Glue and CloudWatch provide native execution status and logs

- EventBridge routes failure events to SNS subscriptions

- Scheduled health checks inspect job freshness and data-count consistency for JDBC jobs

- Datadog receives health telemetry from the scheduled health-check process

- Vela monitoring captures pipeline outcome telemetry

 

## Architectural Strengths

 

- Strong separation of deployment boundaries by source folder

- High reuse through shared modules

- Support for multiple ingestion styles without forcing one implementation model

- Clear operational automation for scheduling, monitoring, and restart behavior

- Good fit for incremental repository growth as new source systems are added

- CI path filtering reduces deployment blast radius

 

## Architectural Trade-offs and Constraints

 

- The repository contains multiple implementation styles, which increases cognitive load

- Some behavior is split between local modules and externally hosted modules, so full understanding requires cross-repository context

- Runtime injection of Terraform common files means the effective Terraform stack is partially assembled during CI rather than stored entirely in each folder

- `jdbc_batch` behaves like a subsystem with its own conventions, which improves flexibility but reduces overall uniformity

- Large `locals.tf` job maps can become difficult to review and maintain at scale

 

## Recommended Mental Model for Navigating the Repository

 

When analyzing or modifying this repository, it is useful to think in five layers:

 

1. Delivery layer: Vela pipeline and CI runtime file injection

2. Source declaration layer: one folder per source domain

3. Reusable infrastructure layer: shared Terraform modules

4. Runtime execution layer: AWS Glue, ECS, triggers, roles, notifications

5. Operations layer: restart scripts, health checks, Datadog, CloudWatch, SNS

 

## Practical Component Map

 

| Layer | What to inspect first | Why it matters |

| --- | --- | --- |

| Delivery | `.vela.py`, `.ci/common-files` | Explains how stacks are executed and how environment context is supplied |

| Standard source folders | `locals.tf`, `main.tf`, `glue.tf` | Shows source intent and the implementation pattern used |

| Shared local module | `modules/glue_job` | Explains common Glue job behavior across many folders |

| JDBC subsystem | `jdbc_batch/locals.tf`, `jdbc_batch/secrets.tf`, `jdbc_batch/modules` | Explains custom JDBC orchestration and notifications |

| Operations | `scripts`, `jdbc_batch/health_check` | Explains restart and monitoring behavior |

 

## Conclusion

 

This repository is not a single monolithic Terraform project. It is a coordinated collection of source-aligned Terraform stacks that share delivery tooling and reusable ingestion modules.

 

The architecture is centered on one principle: keep deployment ownership close to each source system while standardizing the mechanics of AWS Glue-based ingestion. The result is a repository that scales by adding new source folders, supported by a mix of external platform modules, local reusable modules, and a specialized JDBC ingestion subsystem for more complex workloads.

 

## Runtime Behavior Analysis

 

Runtime behavior in this repository is centered on scheduled or event-driven AWS execution units. In practice, three runtime patterns matter most:

 

- Standard Glue-based Talaria ingestion for most source folders

- JDBC workflow-driven ingestion for the jdbc_batch subsystem

- Specialized scheduled tasks for edge cases such as staged file or ECS-driven ingestion

 

The most important operational behavior is not the Terraform apply itself, but what happens after an AWS Glue job, workflow, or ECS task starts running in the target environment.

 

### Runtime Pattern 1: Standard Glue-Based Talaria Jobs

 

This is the dominant runtime model for folders that use either external Talaria modules or the local shared Glue job module.

 

#### Startup Flow

 

At startup, the runtime prepares the job execution environment, resolves dependencies, and establishes network or credential access.

 

Startup flow diagram:

 

Trigger source

→ Glue trigger schedule, manual start, or post-deployment Lambda invocation

→ AWS Glue allocates the runtime container and worker capacity

→ Execution role is assumed

→ Job script is loaded from artifact storage

→ Additional Python packages and jars are loaded

→ Glue connections are attached for network-enabled access

→ Runtime arguments are merged from defaults and source-specific settings

→ Talaria process starts

 

Key startup responsibilities:

 

- Load the correct script version and dependency package set

- Resolve the execution role and access path to S3, Secrets Manager, and Glue catalog services

- Bind the job to the configured source type, such as Kafka, staged files, or unified source mode

- Prepare Iceberg-related arguments such as checkpoint paths, catalog identifiers, and table naming

 

#### Processing Flow

 

During processing, the job reads from its source, applies configured transformations, and writes to the lakehouse target.

 

Processing flow diagram:

 

Source endpoint

→ Source connector initialization

→ Data read from Kafka, staged file, or other configured source

→ Talaria transformations applied

→ Optional schema handling and payload unpacking

→ Record normalization and timestamp handling

→ Iceberg sink writer initialized

→ Data written to S3-backed Iceberg tables

→ Glue catalog metadata updated or referenced

→ Metrics and logs emitted to CloudWatch

 

Common processing behaviors:

 

- Kafka-oriented jobs usually unpack message envelopes, preserve metadata, and split payloads into sink-ready records

- Unified jobs use source and sink arguments to compose a broader end-to-end runtime contract inside a single job

- Flat-file and staged-data jobs interpret source file location and optional data model artifacts before writing to Iceberg

 

#### Shutdown Flow

 

Shutdown behavior is mostly controlled by Glue runtime completion semantics rather than custom shutdown code.

 

Shutdown flow diagram:

 

Processing completes or fails

→ Glue runtime flushes remaining work

→ Final sink commit occurs

→ CloudWatch receives terminal logs and metrics

→ Job state becomes SUCCEEDED, FAILED, STOPPED, or TIMEOUT

→ Registry, trigger, and monitoring systems observe terminal state

→ Next scheduled run waits for future trigger

 

Important shutdown characteristics:

 

- Normal shutdown is a managed Glue completion path after sink writes finish

- Operational shutdown can be forced when a restart workflow stops an already running job before starting a new one

- Retries are intentionally externalized; the shared Glue module sets Glue retries to zero and relies on an external restarter pattern

- If stop-before-start is enabled, a deployment-driven starter can terminate an active run before relaunching it

 

### Runtime Pattern 2: JDBC Workflow-Driven Ingestion

 

The jdbc_batch subsystem has a more explicit runtime model. Instead of treating each job as fully independent, it organizes many table-level Glue jobs into a workflow chain.

 

#### Startup Flow

 

The workflow startup sequence decides which table job runs first and prepares JDBC-specific runtime arguments.

 

Startup flow diagram:

 

Scheduled Glue workflow trigger

→ Source workflow starts

→ First table-level Glue job is selected

→ Glue job container starts

→ JDBC driver and extra libraries are loaded

→ Source secret is read from Secrets Manager

→ JDBC connection string and source table settings are applied

→ Cross-account Iceberg target role is prepared

→ Table extraction job begins

 

Key startup responsibilities:

 

- Resolve source-specific secrets, JDBC driver, and connection settings

- Apply partitioning settings for parallel extraction when configured

- Set target warehouse, target database, and assume-role parameters for lakehouse writes

- Establish workflow context so later jobs can start conditionally after successful completion of previous jobs

 

#### Processing Flow

 

The JDBC jobs perform structured extraction and table-by-table load processing.

 

Processing flow diagram:

 

JDBC source table

→ SQL connection established

→ Source filters, selected fields, and partition rules applied

→ Full or delta extraction performed

→ Records transformed into Iceberg-compatible output

→ Data written to target warehouse path

→ Delta state and job logs updated

→ Job succeeds

→ Conditional trigger starts next table job in workflow

 

Common processing behaviors:

 

- Some jobs run full loads, while others use delta fields and safety windows

- Partition settings improve extraction parallelism for larger tables

- Target writes often use cross-account role assumption into the lakehouse environment

- Sequential chaining reduces overlap risk for table families that need ordered execution

 

#### Shutdown Flow

 

The JDBC platform has both job-level shutdown and workflow-level shutdown.

 

Shutdown flow diagram:

 

Current table job finishes

→ Glue marks terminal state

→ EventBridge observes failure states for alerting

→ SNS notifies subscribed recipients if failure or timeout occurs

→ If success and another table exists, conditional trigger starts next job

→ If success and no next table exists, workflow ends

→ Health-check process later evaluates freshness and record-count consistency

 

Important shutdown characteristics:

 

- A single table job shutdown may immediately transition into the next table job startup

- Workflow shutdown only occurs after the final table job reaches a terminal state

- Failure shutdown is visible through EventBridge and SNS notification routing

- Post-run health validation is deferred to the scheduled health-check process, not embedded directly in the Glue job runtime

 

### Runtime Pattern 3: Specialized Scheduled Tasks

 

Some folders use specialized modules for nonstandard runtime execution, such as Salesforce-to-staging ingestion or ECS-based Talaria tasks.

 

#### Startup Flow

 

Startup flow diagram:

 

Schedule or EventBridge rule

→ ECS task or specialized ingestion module starts

→ Container image is pulled

→ Execution role and network settings are applied

→ External endpoint configuration is injected

→ Talaria command-line process begins

 

#### Processing Flow

 

Processing flow diagram:

 

External API or staged source

→ Data fetched by containerized Talaria runtime

→ Files or payloads written to staging location

→ Follow-on staging-to-Iceberg job reads staged output

→ Transformations applied

→ Lakehouse sink updated

 

#### Shutdown Flow

 

Shutdown flow diagram:

 

Fetch or extraction completes

→ Container exits with success or failure state

→ Scheduler records terminal status

→ Downstream staged-data consumers wait for next scheduled run or manifest availability

 

### Cross-Cutting Runtime Behaviors

 

Regardless of runtime pattern, the repository shows several consistent operational behaviors.

 

#### 1. Dependency Resolution at Runtime

 

Runtime startup depends on remote artifact resolution rather than locally packaged source code in the repository.

 

Flow diagram:

 

Terraform-defined job

→ Artifact path resolved

→ Script and library versions fetched from S3

→ Runtime starts with pinned artifact versions

 

This means the repository controls orchestration and configuration, while executable job logic is largely delivered from shared artifact storage.

 

#### 2. Observability and Monitoring Flow

 

Flow diagram:

 

Running job

→ CloudWatch logs and metrics emitted

→ EventBridge receives state transitions

→ SNS distributes failure notifications where configured

→ Scheduled health-check evaluates selected JDBC jobs

→ Datadog receives summarized health telemetry

 

This creates layered observability:

 

- Native execution telemetry from AWS Glue and CloudWatch

- Event-driven alerting from EventBridge and SNS

- Periodic health assessment from the external health-check process

 

#### 3. Restart and Controlled Interruption Flow

 

Flow diagram:

 

Operational restart request

→ Running Glue job identified

→ Active run stopped if required

→ Wait period observed

→ New job run started

 

This restart behavior is important because it changes shutdown semantics from passive completion to active interruption followed by relaunch.

 

## Runtime Summary

 

The repository’s runtime behavior is built around managed AWS execution rather than long-lived application servers. Startup is driven by schedules, deployment-triggered invocations, or workflow chaining. Processing is mostly Talaria or JDBC extraction logic running inside AWS Glue or specialized tasks. Shutdown is usually a managed terminal state transition, but in some cases it is deliberately controlled by restart automation or workflow chaining.

 

In short:

 

- Startup flow is configuration-heavy and dependency-heavy

- Processing flow is source-adapter and sink-writer centric

- Shutdown flow is AWS-managed, state-driven, and strongly tied to observability and restart controls

 

## Deployment and Operations Analysis

 

### 1. Deployment Process

 

This repository uses folder-scoped Terraform deployment. Each source directory is treated as an independent deployment unit, even though all units share one repository and one delivery framework.

 

#### Deployment Objectives

 

- Limit deployment blast radius to the changed source folder

- Reuse a single CI/CD pattern across many source stacks

- Inject shared Terraform runtime configuration consistently

- Support both review-time planning and automatic apply on merge or push to main

 

#### End-to-End Deployment Flow

 

Deployment flow diagram:

 

Developer change

→ Commit or pull request

→ Vela detects changed folder path

→ AWS credentials generated for pipeline execution

→ Shared Terraform files copied into target folder

→ Terraform plan runs for pull request validation

→ Terraform apply runs on push to main

→ AWS resources created or updated for that folder only

→ Optional post-deployment job start behavior occurs where enabled

 

#### Deployment Boundaries

 

The repository is not deployed as a single root Terraform project. Instead:

 

- Each source folder is the primary change unit

- `jdbc_batch` is its own deployment unit with many contained resources

- Shared Terraform files are injected at pipeline runtime, not stored permanently in each source folder

- The deployment engine is path-sensitive, so unrelated folders normally do not redeploy

 

#### Deployment Characteristics

 

- Pull requests validate infrastructure intent through plan

- Pushes to main perform automatic apply

- The deployment model favors autonomy per source but depends on central pipeline correctness

- Some modules can trigger runtime actions after deployment, such as starting or restarting Glue jobs

 

### 2. CI/CD Flow

 

The CI/CD implementation is driven by Vela, with `.vela.py` as the maintainable source and `.vela.yml` as the rendered operational pipeline.

 

#### CI/CD Stages

 

The delivery model includes several major stage categories:

 

- Lint and repository validation

- Per-folder Terraform plan and apply stages

- Restart automation for operational scripts

- Scheduled health-check execution

- Final monitoring and reporting

 

#### CI/CD Flow Diagram

 

Pull request or push event

→ Lint stage runs repository checks

→ Vela selects stages whose paths match changed folders

→ AWS credential generation step runs

→ Common Terraform files copied into folder

→ Terraform plan or apply executes

→ Optional restart or scheduling stages run for operations-related paths or scheduled events

→ Monitoring stage records overall pipeline outcome

 

#### CI Behavior

 

The CI side emphasizes static quality and deployment readiness.

 

Current CI-oriented controls include:

 

- Folder consistency checks

- Render consistency checks between `.vela.py` and `.vela.yml`

- Pre-commit validation

- Terraform formatting validation

- Terraform documentation generation checks for module directories

 

#### CD Behavior

 

The CD side emphasizes automated folder-scoped application.

 

Characteristics:

 

- Auto-apply occurs on push to main for matching folders

- The same role is used to manage AWS infrastructure changes across source folders

- The repository relies on a Terraform plugin image rather than local runner state

- Monitoring runs regardless of pipeline success or failure, giving centralized delivery telemetry

 

#### Operational Pipelines Beyond Deployment

 

The pipeline also supports operations-related flows beyond standard plan and apply:

 

- Manual or scripted restart support for selected Glue jobs

- Scheduled JDBC health-check execution

- Delivery telemetry export through a final monitoring stage

 

### 3. Testing Strategy

 

The repository’s testing strategy is primarily infrastructure-centric and operationally oriented rather than application-unit-test oriented.

 

#### Testing Layers

 

##### A. Static Validation

 

This is the most consistently enforced testing layer.

 

It includes:

 

- YAML validation

- Terraform formatting checks

- Terraform documentation checks for modules

- Repository consistency checks in CI

 

Purpose:

 

- Catch structural and formatting issues before deployment

- Keep reusable modules documented and standardized

 

##### B. Plan-Based Infrastructure Validation

 

Terraform plan on pull requests functions as the main pre-deployment verification mechanism.

 

Purpose:

 

- Show intended infrastructure drift before apply

- Surface invalid references, provider issues, and input mismatches early

- Allow reviewers to assess infrastructure impact before merge

 

##### C. Dedicated Integration Stacks

 

The repository contains dedicated testing-oriented folders such as `integration_tests` and `mif_tests`.

 

These folders indicate support for controlled runtime validation of:

 

- Staging-to-Iceberg behavior

- Kafka-to-Iceberg behavior

- CSV-oriented ingestion behavior

- JDBC sink behavior

- Temporary or experimental Glue job testing

 

Purpose:

 

- Validate end-to-end ingestion patterns in a live AWS environment

- Exercise real Talaria runtime combinations and source/sink configurations

 

##### D. Operational Health Validation

 

The JDBC health-check process acts as a post-deployment operational testing layer.

 

Purpose:

 

- Detect stale jobs

- Compare source and target record counts where observable

- Surface production-like operational issues after deployment

 

#### Testing Strategy Assessment

 

Strengths:

 

- Strong real-environment validation model

- Good support for integration-style testing of ingestion patterns

- Static checks are automated and centralized

 

Limitations:

 

- Little evidence of conventional unit-test coverage inside the repository

- Runtime validation depends heavily on AWS execution rather than isolated local tests

- Some test jobs are intentionally temporary, which can reduce long-term repeatability

 

#### Practical Testing Model

 

Testing flow diagram:

 

Author change

→ Static checks run

→ Terraform plan validates infrastructure intent

→ Test-oriented stacks can be deployed for runtime validation

→ Operational health checks validate behavior after deployment

 

### 4. Dependency Analysis

 

Deployment and operations in this repository depend on a layered chain of internal and external systems.

 

#### Dependency Categories

 

##### A. Delivery Dependencies

 

- Vela pipeline engine

- Render relationship between `.vela.py` and `.vela.yml`

- Terraform plugin runner image

- AWS credential generation mechanism

- Shared CI runtime file injection from `.ci/common-files`

 

These dependencies control whether a folder can be deployed at all.

 

##### B. Infrastructure Dependencies

 

- Terraform AWS provider

- AWS account permissions and IAM roles

- Artifact storage for job scripts and libraries

- Glue connections for VPC or private-source access

 

These dependencies control whether infrastructure can be provisioned successfully.

 

##### C. Runtime Dependencies

 

- AWS Glue

- S3

- Secrets Manager

- Glue catalog

- EventBridge

- Lambda

- CloudWatch

- SNS

- DynamoDB

- ECS for specialized tasks

 

These dependencies control whether deployed jobs actually run correctly.

 

##### D. External Platform Dependencies

 

- External Talaria Terraform modules

- Talaria runtime artifact versions

- Schema registry endpoints

- Kafka brokers

- Source databases and APIs

- Downstream lakehouse IAM roles and storage endpoints

 

These dependencies are critical because many core behaviors are not fully implemented inside this repository itself.

 

#### Dependency Flow Diagram

 

Repository configuration

→ Vela pipeline

→ Terraform execution environment

→ AWS infrastructure provisioning

→ Runtime artifact resolution

→ Source connectivity and target lakehouse access

→ Monitoring and health systems

 

#### Dependency Risk Concentrations

 

The highest dependency concentration appears in these areas:

 

- External shared modules, because they hide significant runtime behavior outside the repository

- Artifact versioning, because deployed job logic is resolved from S3 paths at runtime

- AWS IAM and cross-account role assumptions, because both deployment and runtime depend on them

- Shared CI runtime injection, because missing or incorrect injected files can break folder-level deployments

 

### 5. Change Impact Analysis

 

Change impact in this repository is highly sensitive to where a change is made.

 

#### Impact Model by Change Location

 

##### A. Source Folder Changes

 

Typical impact:

 

- Usually isolated to one source domain

- May change job definitions, schedules, arguments, or target destinations

- May trigger Glue job recreation or restart behavior

 

Risk level: Low to medium, depending on whether the change affects runtime arguments, IAM, or target locations.

 

##### B. Shared Module Changes

 

Typical impact:

 

- Affects every source folder that depends on the changed module

- Can change Glue defaults, scheduling behavior, IAM assumptions, artifact resolution, or runtime argument composition

- Can produce broad runtime side effects even when only one module file changed

 

Risk level: High.

 

##### C. CI/CD Pipeline Changes

 

Typical impact:

 

- Can affect all folders in the repository

- May alter credential generation, validation logic, plan/apply behavior, or runtime file injection

- Can block all deployments if misconfigured

 

Risk level: Very high.

 

##### D. `jdbc_batch` Core Changes

 

Typical impact:

 

- Can affect many JDBC ingestion jobs at once

- May change workflow sequencing, notifications, secret usage, or shared local defaults

- Can cause broad operational issues across multiple source systems

 

Risk level: High.

 

##### E. Operations Script and Health-Check Changes

 

Typical impact:

 

- Usually do not change provisioning directly

- Can change incident response, restart semantics, or monitoring fidelity

- Can create false positives or missed alerts if modified incorrectly

 

Risk level: Medium to high.

 

#### Change Impact Flow Diagram

 

Code change location

→ Determines affected deployment scope

→ Determines whether impact is local, shared, or global

→ Influences review depth required

→ Influences need for runtime validation and operational observation

 

#### Recommended Review Heuristics

 

| Change Type | Likely Blast Radius | Review Priority | Suggested Validation |

| --- | --- | --- | --- |

| Single source folder | Local | Standard | Plan review plus source-specific runtime check |

| `modules/glue_job` | Multi-source | High | Plan review across representative folders plus runtime validation |

| `.vela.py`, `.vela.yml`, `.ci/common-files` | Repository-wide | Critical | CI validation plus representative deployment simulation |

| `jdbc_batch/modules` or `jdbc_batch/locals.tf` | JDBC subsystem-wide | High | Review workflow behavior, secrets, notifications, and representative test execution |

| Health-check or restart scripts | Operations-wide | High | Operational dry run or controlled validation in dev |

 

### 6. Operational Runbooks

 

The repository already contains operational implementation elements, but the logic can be turned into practical runbooks.

 

#### Runbook A: Deploy a Source Change

 

Objective:

 

- Safely release a change to one source folder

 

Procedure summary:

 

1. Confirm the change is limited to the intended folder or shared component.

2. Review Terraform plan output in the pull request.

3. Validate whether job restart or start-on-change behavior is expected.

4. Merge or push to main.

5. Confirm apply completed successfully.

6. Verify updated AWS resources and observe first runtime execution.

 

Success signals:

 

- Plan is consistent with intended change

- Apply succeeds

- Job appears with expected configuration or updated schedule

- First run reaches expected terminal state

 

#### Runbook B: Investigate a Failed Glue Job

 

Objective:

 

- Determine whether failure is caused by deployment, source connectivity, permissions, or runtime logic

 

Procedure summary:

 

1. Identify the affected source folder and job type.

2. Check recent pipeline runs to see whether a deployment introduced the issue.

3. Review CloudWatch logs and Glue terminal status.

4. Confirm source secret, source endpoint, and network connectivity assumptions.

5. Confirm target bucket, catalog, and assume-role access.

6. Determine whether the issue is isolated or shared across multiple jobs.

 

Decision guide:

 

- If only one source folder is affected, start with that folder’s local configuration.

- If many jobs fail similarly, inspect shared modules, shared artifacts, or shared infrastructure dependencies.

 

#### Runbook C: Restart a Stuck or Long-Running Job

 

Objective:

 

- Safely stop and relaunch an active job when operationally required

 

Procedure summary:

 

1. Confirm the job is currently running and requires interruption.

2. Stop the active Glue run.

3. Allow a short wait period for shutdown propagation.

4. Start a new run.

5. Observe logs and state transition after restart.

 

Risks:

 

- In-flight processing may be interrupted

- Restart may mask the underlying root cause if logs are not reviewed first

 

#### Runbook D: Validate JDBC Workflow Health

 

Objective:

 

- Confirm that workflow sequencing and data movement remain healthy

 

Procedure summary:

 

1. Identify the JDBC source workflow.

2. Review whether the first scheduled job triggered as expected.

3. Check whether downstream jobs were conditionally triggered in sequence.

4. Review EventBridge and SNS evidence for failure notifications.

5. Review health-check output for freshness, counts, and error indicators.

 

Success signals:

 

- Jobs run in expected order

- No unexpected workflow gaps

- Health-check status is good or within expected tolerance

 

#### Runbook E: Assess High-Risk Shared Changes

 

Objective:

 

- Reduce blast radius from shared module or pipeline modifications

 

Procedure summary:

 

1. Classify the change as module-level, pipeline-level, or JDBC-core-level.

2. Identify all dependent folders or workflows.

3. Review representative plan outputs.

4. Validate in representative dev scenarios before broad rollout.

5. Monitor early post-deployment runs closely.

 

### 7. Knowledge Graph

 

The following text-based knowledge graph summarizes the deployment and operations topology.

 

#### Knowledge Graph: Delivery and Deployment

 

Repository

→ contains → source folders

→ contains → shared module `modules/glue_job`

→ contains → `jdbc_batch` subsystem

→ contains → CI definitions

→ contains → operations scripts

 

`.vela.py`

→ renders → `.vela.yml`

→ defines → lint stage

→ defines → per-folder Terraform stages

→ defines → restart stage

→ defines → scheduled health-check stage

→ defines → monitoring stage

 

`.ci/common-files`

→ injects → provider configuration

→ injects → repo_name variable

→ injects → derived environment locals

 

Pull request event

→ triggers → lint stage

→ triggers → Terraform plan for changed folders

 

Push to main

→ triggers → Terraform apply for changed folders

 

#### Knowledge Graph: Provisioning and Runtime

 

Source folder

→ depends on → local module or external Talaria module

→ provisions → Glue jobs, triggers, roles, or workflows

 

`modules/glue_job`

→ creates → Glue job

→ may create → IAM role

→ may create → Glue trigger

→ creates → registry entry in DynamoDB

→ may invoke → Glue starter Lambda

 

`jdbc_batch`

→ uses → source orchestration module

→ uses → source-table module

→ uses → target orchestration module

→ uses → target-table module

→ uses → notification subscription module

 

JDBC source module

→ creates → SNS topic

→ creates → EventBridge rule

→ creates → Glue workflow

→ expands into → multiple table-level Glue jobs

 

#### Knowledge Graph: Operations and Observability

 

Glue job

→ emits → CloudWatch logs

→ emits → Glue state transitions

→ may read → Secrets Manager secrets

→ may use → Glue network connections

→ writes → S3 and Iceberg targets

 

EventBridge

→ observes → Glue state changes

→ forwards failure events to → SNS

 

SNS

→ notifies → subscribed recipients

 

Health-check process

→ queries → Glue job runs

→ reads → CloudWatch logs

→ evaluates → freshness and record-count signals

→ sends → Datadog telemetry

 

Restart script

→ inspects → active Glue runs

→ stops → running jobs when required

→ starts → new Glue runs

 

#### Knowledge Graph: Impact Relationships

 

Shared module change

→ impacts → many source folders

 

Pipeline change

→ impacts → all deployments

 

Source folder change

→ usually impacts → one deployment unit

 

`jdbc_batch` core change

→ impacts → many JDBC jobs and workflows