```
Analyze repository conventions, onboarding patterns and implementation processes.

Document:

1. New Kafka Topic Onboarding
2. New Glue Job Creation
3. New Source System Onboarding
4. Terraform Entry Creation
5. Deployment Process
6. PR Process
7. Promotion Process

For each process provide:

- Inputs
- Outputs
- Files Modified
- Validation Rules
- Common Mistakes
- Step-by-Step Procedure

Generate markdown documentation only.
```



# Repository Conventions, Onboarding Patterns, and Implementation Processes

 

## Purpose

 

This document explains how work is typically introduced into this repository based on the conventions visible in the codebase. It focuses on the practical implementation patterns for onboarding Kafka topics, Glue jobs, source systems, Terraform entries, deployment changes, pull requests, and environment promotion.

 

This repository is a development-environment infrastructure repository. Where promotion is discussed, the guidance is based on conventions visible here, especially the environment suffix logic and naming model, not on direct evidence of sibling `snd` or `prod` repositories in this workspace.

 

---

 

## Repository Conventions Summary

 

### Core Structural Conventions

 

- One source system or dataset family is usually represented by one top-level folder.

- Each deployable folder is expected to be listed in `.vela.py`.

- Vela deploys by changed folder path, not by a single global Terraform root.

- Shared Terraform runtime files are injected by CI from `.ci/common-files`.

- Most source folders use one of two patterns:

  - `main.tf` plus `locals.tf` with an external Talaria module

  - `glue.tf` plus `locals.tf` with the local `modules/glue_job` module

- The `jdbc_batch` folder is a special subsystem with its own orchestration pattern.

 

### Naming Conventions

 

- Repository environment is derived from repository name suffix such as `dev`, `snd`, or `prod`.

- Source topics usually end with `.raw` for raw-layer ingestion.

- Sink databases usually follow one of these shapes:

  - `minerva_<env>_src_<domain>_<source>_prd_raw_db`

  - `lh_<source>_raw_<env>`

  - `lh_<source>_report_raw_<env>`

- Warehouse paths usually include `/raw/`.

- Folder name usually becomes the default source-system identity in CI-injected locals.

 

### Delivery Conventions

 

- `.vela.py` is the authoritative pipeline source.

- `.vela.yml` is rendered output and should not be manually maintained.

- Pull requests run plan-oriented validation.

- Pushes to `main` run apply for changed folders.

- CI validation checks that `.vela.py` contains all expected repository folders.

 

---

 

# 1. New Kafka Topic Onboarding

 

## Inputs

 

- source system name

- business domain or ownership context

- Kafka topic name

- schema grain or business object name

- Confluent or Kafka connection details

- schema registry endpoint details

- secret name for Kafka credentials

- target raw lakehouse database

- target warehouse path

- target assume-role ARN

- scheduling requirement

- Talaria job type and version

 

## Outputs

 

- updated source folder configuration containing a new job entry or module block

- Kafka-to-Iceberg ingestion definition for the new topic

- schedule configuration if recurring execution is needed

- lakehouse target mapping for the new topic

- deployable Terraform change scoped to the source folder

 

## Files Modified

 

Typical local-module pattern:

 

- source-folder `locals.tf`

- source-folder `glue.tf`

 

Possible external-module pattern:

 

- source-folder `main.tf`

- source-folder `locals.tf`

 

Sometimes also:

 

- source-folder data model files for flat-file variations

- `.vela.py` and `.vela.yml` only if a brand-new folder is created rather than adding a topic to an existing folder

 

## Validation Rules

 

- topic name should follow the existing raw-topic convention used by the source folder

- sink database should remain aligned to the source folder’s raw database pattern

- sink warehouse path should remain aligned to the source folder’s raw storage path

- schema registry endpoint should match the correct environment map

- Kafka secret name should match environment and source-system naming conventions

- job type must match one of the supported Glue module job types if using `modules/glue_job`

- schedule must be valid cron syntax when scheduling is required

- job naming should remain source-specific and grain-specific

 

## Common Mistakes

 

- using the wrong environment-specific Kafka endpoint or schema registry endpoint

- creating a topic entry with naming inconsistent with existing jobs in the same folder

- pointing the topic to the wrong lakehouse database or S3 warehouse path

- forgetting required transforms such as timestamp handling or Kafka unpacking where the folder convention expects them

- mixing local module conventions with external Talaria module conventions in the same folder without intent

- hardcoding environment-specific values inconsistently with the folder’s local maps

 

## Step-by-Step Procedure

 

1. Identify whether the source folder uses the local `modules/glue_job` pattern or an external Talaria module pattern.

2. If the topic belongs to an existing source folder, reuse that folder instead of creating a new one.

3. Open the source folder’s `locals.tf` and inspect the existing `glue_jobs` map or module configuration style.

4. Add a new job definition for the new topic by following the nearest existing topic pattern in that folder.

5. Set the Kafka topic name using the existing raw-layer naming convention.

6. Set or confirm the Kafka endpoint, secret name, and schema registry endpoint mappings.

7. Set the sink database, warehouse path, checkpoint directory, and assume-role values using the same source-family pattern.

8. Add or confirm transforms such as timestamp normalization, Kafka unpacking, and schema-based split behavior if that is how the folder currently works.

9. Update `glue.tf` only if the folder requires new module wiring rather than just a new `locals.tf` entry.

10. Validate formatting and plan behavior through the normal PR flow.

11. After merge, confirm that only the intended folder deploys and that the new Glue job is created or updated.

 

---

 

# 2. New Glue Job Creation

 

## Inputs

 

- job purpose

- job type such as `unified`, `unified_batch`, `kafka_to_iceberg`, or another supported pattern

- job version

- source parameters

- sink parameters

- worker sizing and concurrency needs

- schedule requirement

- IAM role or role reuse decision

- secret requirements

- optional extra Python libraries or jars

 

## Outputs

 

- new Glue job Terraform definition

- optional trigger definition

- optional Lambda start-on-change behavior

- updated source-specific runtime argument set

- deployable folder-scoped Terraform change

 

## Files Modified

 

Most common pattern:

 

- source-folder `locals.tf`

- source-folder `glue.tf`

 

Shared-module changes only if repository capability is missing:

 

- `modules/glue_job/variables.tf`

- `modules/glue_job/locals.tf`

- `modules/glue_job/glue.tf`

- related module files if behavior must be extended

 

## Validation Rules

 

- selected job type must be supported by the shared Glue module when using that module

- job version must point to a valid artifact naming scheme

- script and runtime behavior must match the selected job type

- source and sink arguments must be internally coherent

- log and metric settings should remain enabled unless there is a clear exception

- schedule should be empty only when intentionally unscheduled

- role settings should be explicit and consistent with existing source patterns

 

## Common Mistakes

 

- creating a new job in `locals.tf` but not ensuring `glue.tf` iterates over that map correctly

- choosing the wrong job type for the intended source behavior

- forgetting to set sink arguments required by the chosen runtime pattern

- setting job version or extra libraries inconsistently with the selected script type

- introducing a shared-module change when a local folder-only change would have been sufficient

- failing to consider blast radius when modifying `modules/glue_job`

 

## Step-by-Step Procedure

 

1. Determine whether the new job can be created inside an existing source folder.

2. Identify the pattern already used by that folder.

3. If the folder uses `modules/glue_job`, add a new entry to the `glue_jobs` map in `locals.tf`.

4. Set `job_type`, `job_version`, scheduling, source arguments, sink arguments, and optional runtime tuning values.

5. Confirm `glue.tf` already wires `for_each = local.glue_jobs`; if not, align with the folder’s chosen pattern.

6. If the job requires behavior not supported by the current module inputs, evaluate whether the change belongs in the source folder or in `modules/glue_job`.

7. Avoid modifying the shared module unless multiple folders will benefit or the capability is truly cross-cutting.

8. Run the normal PR validation path and review the plan carefully.

9. After deployment, confirm the Glue job appears with expected trigger, arguments, and runtime behavior.

 

---

 

# 3. New Source System Onboarding

 

## Inputs

 

- source system identifier

- business function and subgroup ownership

- ingestion mode such as Kafka, JDBC, staging, flat file, or specialized task

- destination raw lakehouse database and warehouse path

- source connectivity method

- credentials and secret names

- expected schedule cadence

- preferred Terraform pattern based on similarity to existing folders

- IAM requirements

 

## Outputs

 

- new top-level source folder

- source-specific Terraform definitions

- deployment-stage entry in Vela

- folder recognized by repository validation

- deployable source-scoped infrastructure unit

 

## Files Modified

 

Required for a new folder:

 

- new source folder `locals.tf`

- new source folder `glue.tf` or `main.tf`

- possibly additional source files such as `salesforce.tf`, data model files, or other source-specific files

- `.vela.py`

- `.vela.yml` after rendering from `.vela.py`

 

Sometimes:

 

- `CODEOWNERS` if ownership rules need to change

- module files only if the source requires a new shared capability

 

## Validation Rules

 

- new folder must be included in `.vela.py` folder list

- rendered `.vela.yml` must match `.vela.py`

- folder naming should be consistent with other top-level source folders

- `ent_func` and `subgroup` should be defined in the new folder’s `locals.tf`

- the source folder should use a recognized repository pattern

- repository-level CI checks must continue to pass

 

## Common Mistakes

 

- creating a new folder but forgetting to add it to `.vela.py`

- editing `.vela.yml` directly instead of updating `.vela.py` and rendering

- choosing a folder structure that does not match an existing deployable pattern

- hardcoding environment values instead of relying on injected locals and repository suffix logic

- over-customizing the first version instead of starting from the nearest existing source template

 

## Step-by-Step Procedure

 

1. Identify the nearest comparable existing source folder by ingestion type and business domain.

2. Create a new top-level folder using the source-system name.

3. Add `locals.tf` with ownership fields such as `ent_func` and `subgroup`.

4. Choose one of the repository’s established patterns:

   - external module wrapper with `main.tf`

   - local Glue job map with `glue.tf`

   - specialized task pattern if clearly justified

5. Add the source-specific configuration files needed for the chosen pattern.

6. Populate source connection settings, sink targets, schedules, and role names using the nearest existing example.

7. Add the new folder name to the `FOLDERS` list in `.vela.py`.

8. Render `.vela.yml` from `.vela.py`.

9. Validate that CI folder consistency logic will recognize the new folder.

10. Open a PR, review the plan, and deploy via the standard process.

 

---

 

# 4. Terraform Entry Creation

 

## Inputs

 

- target folder

- chosen repository pattern

- module source reference

- module arguments

- ownership metadata

- deployment scope decision

 

## Outputs

 

- new or updated Terraform entry point inside a folder

- module invocation or job-map entry consistent with folder style

- deployable Terraform unit recognized by Vela

 

## Files Modified

 

Depending on the pattern:

 

- source-folder `main.tf`

- source-folder `glue.tf`

- source-folder `locals.tf`

 

If new folder:

 

- `.vela.py`

- `.vela.yml`

 

If shared behavior changes:

 

- files under `modules/glue_job`

- CI common files only if environment or provider conventions truly need to change

 

## Validation Rules

 

- Terraform entry should align to one of the repository’s existing patterns

- source module path should be valid and intentionally chosen

- module arguments should match the pattern’s expected inputs

- locals referenced by the Terraform entry should exist in the folder or in CI-injected common files

- entry should keep folder deployment scope local unless intentionally shared

 

## Common Mistakes

 

- mixing unrelated patterns in the same folder

- referencing locals that only exist in another folder

- adding a Terraform file that changes shared behavior unintentionally

- forgetting that common provider and environment files are injected by CI, not always stored in-folder

- creating a Terraform entry in a new folder without Vela registration

 

## Step-by-Step Procedure

 

1. Decide whether the change belongs in an existing folder or a new one.

2. Select the closest existing folder pattern and mirror its entry structure.

3. Add or update `main.tf` or `glue.tf` depending on the chosen pattern.

4. Confirm that the required locals are present in `locals.tf`.

5. If needed, rely on `.ci/common-files` conventions rather than duplicating provider or repo-name logic manually.

6. If the folder is new, register it in `.vela.py` and regenerate `.vela.yml`.

7. Validate the Terraform plan through the PR process.

 

---

 

# 5. Deployment Process

 

## Inputs

 

- merged change on `main` or push to `main`

- changed folder path

- valid Terraform configuration in that folder

- generated AWS credentials from the pipeline

- rendered `.vela.yml` consistent with `.vela.py`

 

## Outputs

 

- Terraform apply for the changed folder

- created or updated AWS resources

- optional post-deployment Glue start or restart behavior depending on module settings

- monitoring telemetry for pipeline outcome

 

## Files Modified

 

Normally no new file modifications during deployment itself, but deployment depends on:

 

- `.vela.py`

- `.vela.yml`

- `.ci/common-files/*`

- changed source folder files

 

Pipeline runtime also injects:

 

- `.ci/common-files/*.tf` into the folder during execution

 

## Validation Rules

 

- only changed folders should trigger corresponding Terraform stages

- source folder must exist in `.vela.py`

- plan should have been reviewed before apply when change came through PR

- shared-module and pipeline changes should receive higher scrutiny than local folder changes

- environment suffix logic must remain coherent with repository name

 

## Common Mistakes

 

- assuming the whole repository deploys together

- changing `.vela.py` but not rendering `.vela.yml`

- forgetting that CI copies shared Terraform files into the folder during runtime

- underestimating the blast radius of shared module or pipeline changes

- not checking whether the module triggers a post-deployment job start

 

## Step-by-Step Procedure

 

1. Merge the approved PR or push the intended change to `main`.

2. Let Vela evaluate changed paths.

3. Confirm that only the expected folder stages are selected.

4. Allow credential generation and common-file injection to complete.

5. Let Terraform apply run for the changed folder.

6. Review apply success and inspect any resource recreation carefully.

7. Confirm whether the change should have caused a job start or restart.

8. Verify the first runtime execution or resulting AWS resource state.

 

---

 

# 6. PR Process

 

## Inputs

 

- branch containing Terraform or pipeline changes

- changed source folder or shared component

- rendered `.vela.yml` if `.vela.py` changed

- formatted Terraform and documentation updates where required

 

## Outputs

 

- lint and validation results

- Terraform plan for impacted folders

- review feedback from approvers

- approved or rejected infrastructure change

 

## Files Modified

 

Typical PR scope may include:

 

- one or more source folders

- `.vela.py`

- `.vela.yml`

- `modules/glue_job/**`

- `.ci/common-files/**`

- `jdbc_batch/**`

- documentation files

 

## Validation Rules

 

- `.vela.py` must remain consistent with actual top-level folder set

- `.vela.yml` must match rendered `.vela.py`

- YAML checks must pass

- Terraform formatting must pass

- module documentation checks must pass where applicable

- CODEOWNERS approval expectations should be respected

- plan output should match intended blast radius

 

## Common Mistakes

 

- forgetting to regenerate `.vela.yml` after editing `.vela.py`

- making a shared change while reviewing it as if it were folder-local

- ignoring plan output for resources that will be recreated or rescheduled

- assuming formatting and docs checks apply only to source folders and not modules

- failing to call out operational consequences such as restart-on-change behavior

 

## Step-by-Step Procedure

 

1. Create a branch with the intended repository change.

2. Apply the change using the nearest existing repository pattern.

3. If `.vela.py` changed, render `.vela.yml` from it.

4. Ensure formatting and repository checks are clean.

5. Open the PR with a summary of scope, affected folders, and runtime intent.

6. Review CI results, especially plan output and any validation failures.

7. Request or wait for the required reviewers under `CODEOWNERS`.

8. Resolve feedback and re-run validation as needed.

9. Merge only after the blast radius and plan output are understood.

 

---

 

# 7. Promotion Process

 

## Inputs

 

- already validated change in the development repository

- confirmed runtime behavior in development

- target environment repository or branching model for `snd` or `prod`

- environment-specific values such as accounts, roles, endpoints, schedules, and warehouse targets

- approval to promote

 

## Outputs

 

- equivalent change prepared for the next environment

- environment-correct Terraform configuration in the target repository

- promoted deployment after review and apply in that environment

 

## Files Modified

 

Based on repository conventions, promotion would usually involve modifying the corresponding files in the sibling environment repository, not reusing this repository directly.

 

Likely files in the target environment repository:

 

- corresponding source folder `locals.tf`

- corresponding source folder `glue.tf` or `main.tf`

- `.vela.py` and `.vela.yml` only if the source is new in that environment repository

- any environment-specific operational or secret references

 

## Validation Rules

 

- environment suffix must match the target repository name

- environment-specific endpoints, accounts, and role ARNs must be correct for the target environment

- sink warehouse and database targets must point to the right environment

- promotion should only proceed after successful dev validation

- promotion should preserve folder structure and naming conventions unless there is an intentional environment-specific exception

 

## Common Mistakes

 

- copying dev values directly into the next environment without replacing account IDs, roles, endpoints, or buckets

- promoting before observing successful dev runtime behavior

- assuming promotion is automatic from this repository alone

- changing implementation pattern between environments without clear reason

- forgetting to include new folders in the target environment’s `.vela.py`

 

## Step-by-Step Procedure

 

1. Complete the change in the development repository and validate deployment and runtime behavior.

2. Identify the equivalent target environment repository that follows the same naming and folder conventions.

3. Port the change to the corresponding folder in that repository.

4. Replace environment-specific values such as accounts, buckets, roles, checkpoints, and endpoints.

5. If the source folder is new in the target repository, add it to that repository’s `.vela.py` and render `.vela.yml`.

6. Open a PR in the target environment repository and review the target-environment plan output.

7. Apply the same validation and approval discipline used in development.

8. Deploy to the target environment and verify the first successful runtime execution.

 

---

 

## Quick Decision Guide

 

| Task | Usually Modify Existing Folder? | Usually Requires `.vela.py` Update? | High Blast Radius? |

| --- | --- | --- | --- |

| Add Kafka topic to existing source | Yes | No | Low |

| Add new Glue job to existing source | Yes | No | Low to medium |

| Add new source system | No, create new folder | Yes | Medium |

| Add shared module capability | No | No | High |

| Change pipeline behavior | No | Yes | Very high |

| Promote validated source change | In target environment repo | Maybe | Medium to high |

 

---

 

## Final Guidance

 

The safest way to work in this repository is to treat every change as belonging to one of three scopes:

 

- local source-folder scope

- shared module scope

- pipeline scope

 

Most onboarding work should stay local to one source folder and mirror an existing pattern as closely as possible. New folders require Vela registration. Shared-module and pipeline changes require stronger review because they can impact many source systems at once. Promotion should be treated as a separate environment-repository activity after development validation, not as an implicit side effect of a dev-only change.