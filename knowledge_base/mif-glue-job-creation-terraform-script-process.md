# Glue job terraform job script/entry creation process ( step-by-step )
- The goal is to collect the required parameters and generate a consistent Terraform job entry.

 

--Name of the topic, you want to create/modify the terraform job script/entry
   Pattern: {environment}.{source-system}.{schema-grain}.raw
   for example : dev.saptcc.multi-1.raw   , dev.saptcc.cdhdr.raw
   -check validation pattern
   - name of the topic should be taken as source_kafka_topic in glue_job_arguments block

 

   ### extract {source-system}

 

   - source system - check if already exists or new one need to be created.
   a) if already exists , need to add terraform job script/entry in existing locals.tf of that source_folder i.e. folder with <source_system> name

   b) if not exists , 
     - create a new folder with <source_system> name ,for example: `saptce/`, `wahoo/`, `yongyou/`
   - create `locals.tf` and `glue.tf` matching repo patterns.

-- Job Name (logical name)
    Pattern : `kafka-to-iceberg-batch-<source>-<stream>`
  - Example: kafka-to-iceberg-batch-saptce-multi-1, kafka-to-iceberg-batch-saptce-acdoca
    - Must be unique within the folder’s `glue_jobs` map.

 

-- Worker Type
     Allowed : `G.1X`,`G.2X`,`G.4X`,
   Default : `G.1X`

 

-- Number of workers
    Allowed : upto 10
    Default : 1

-- Job Type.
     Allowed : Manual or Scheduled (cron)
     Default : Manual ( for now)

-- source
     Allowed : kafka
   Default : kafka

 

-- Enterprice 
     Allowed : AGTR, FOOD, SPEC
   Default : AGTR

 

-- subgroup 
     Allowed : apac, na, latam
   Default : apac

 

-- Sink/Target Type
      Allowed : iceberg
    Default : iceberg

 

-- Target Database
      Pattern : lh_<source_system_hyphenated>_raw_{source-data-environment}
    Example : lh_cdp_sap_tc1_raw_dev, lh_sap_tcc_raw_prd





 

Rules :

 

## 1) Job identity and versioning

 

These map to the top-level job entry in `locals.tf` and module inputs in `glue.tf`.

 

1. **Job key / name (logical name)**
   - Example: `kafka-to-iceberg-batch-<source>-<stream>`
   - Must be unique within the folder’s `glue_jobs` map.

 

2. **Environment(s) to support**
   - Usually `dev` and `prod` (the repo often uses `local.env` to select endpoints).

 

3. **Talaria job version** (`job_version`)
   - Default: `0.3.0`
   - This controls which Talaria script/library artifacts are used.

 

4. **Job type** (`job_type`)
   - Default: `unified`
   - (Other options exist in the module: `unified_batch`, `kafka_to_iceberg`, etc.)

 

---

 

## 2) Operational sizing and execution

 

1. **Worker type** (`worker_type`)
   - Example: `G.2X`

 

2. **Number of workers** (`number_of_workers`)
   - Example: `4`

 

---

 

## 3) Scheduling (how/when it runs)

 

Scheduling is controlled by the optional `trigger_schedule` field in the job entry.

 

1. **Run mode**
   - Manual (no schedule)
   - Scheduled (cron)

 

2. If scheduled: **cron expression** (`trigger_schedule`)
   - Example: `cron(0 1 * * ? *)`

 

---

 

## 4) Dataflow inputs: Kafka source (required for this pattern)

 

These become Talaria arguments under `glue_job_arguments`.

 

1. **Kafka bootstrap endpoint per environment**
   - dev endpoint
   - prod endpoint

 

2. **Kafka secret name**
   - Example pattern: `minerva-${env}-corp-mif-<source>-gluejob-sa-cc-api-creds`

 

3. **Kafka topic name pattern**
   - Example: `${env}.<source>.multi-1.raw`
   - Collect the exact topic(s) to consume.

 

**Validation your chatbot should do:**

 

- Topic naming: ensure you’re consistent with `.raw` naming if downstream expects raw.
- If the topic differs between envs, collect both explicitly.

 

---

 

## 6) Transformations (Talaria pipeline steps)

 

This job uses two transformers. Your chatbot should support:

 

- “Use default transformer chain (recommended)”
- or “Customize transformers”

 

### 6.1 Transformer 1: timestamp

 

- Enable timestamp transformer? (yes/no)
- Column name (default: `processing_timestamp`)
- Value format (default: `json`)

 

Terraform mapping:

 

- `--transformer1 = timestamp`
- `--transformer1_column = <column>`
- `--transformer1_value_format = <format>`

 

### 6.2 Transformer 2: kafka_unpack

 

- Enable kafka unpack? (yes/no)
- Metadata output column (default: `__metadata__`)

 

Terraform mapping:

 

- `--transformer2 = kafka_unpack`
- `--transformer2_metadata_column = <column>`

 

---

 

## 7) Sink pre-processing: Schema Registry split (recommended)

 

This pattern uses `kafka_split` before writing to Iceberg.

 

1. **Schema Registry endpoint per environment**
   - dev endpoint
   - prod endpoint

 

2. **Schema Registry secret name**
   - Often the same as Kafka secret name.

 

Terraform mapping:

 

- `--sink_transformer1 = kafka_split`
- `--sink_transformer1_schema_registry_endpoint = <endpoint>`
- `--sink_transformer1_secret_name = <secret>`

 

---

 

## 8) Sink outputs: Iceberg configuration (required)

 

These are the most important values because they define where the data lands.

 

1. **Iceberg catalog type**
   - For this repo pattern: `glue`

 

2. **Glue Catalog account ID per environment** (`--sink_iceberg_catalog_id`)
   - dev account ID
   - prod account ID

 

3. **Target Iceberg database name** (`--sink_iceberg_database`)
   - Example: `minerva_dev_src_agtr_saptce_prd_raw_db`

 

4. **Iceberg warehouse S3 prefix** (`--sink_iceberg_warehouse`)
     Pattern : `s3://minerva-${env}-src-${env}/current/prd/raw/sap_tce/`
   - Example: `s3://minerva-${env}-src-${env}/current/prd/raw/sap_tce/`

 

5. **Checkpoint directory S3 prefix** (`--sink_iceberg_checkpoint_dir`)
   - Example: `s3://minerva-${env}-glue-checkpoints/checkpoints/unified/`

 

6. **Assume role ARN** for writing to the sink (`--sink_iceberg_assume_role_arn`)
   - Collect the exact ARN pattern per environment if it differs.

 

7. **Assume role session name** (`--sink_iceberg_assume_session_name`)
   - Example: `mif-glue-iceberg`

 

**Validation:**

 

- S3 paths must end with `/` (recommended) for consistent prefix handling.
- Confirm that the database name and warehouse match the intended domain (dev vs prod).
- Confirm the assume-role account matches the sink catalog/warehouse account.

 

 

---

 

## 11) Output: should generate terraform script

 

A new entry/script under `glue_jobs` should looks like below:

 

```
"<job-key>" = {
  job_type     = "unified"
  job_version  = "<talaria-version>"
  glue_version = "5.1"

 

  number_of_workers = 4
  worker_type       = "G.2X"
  stop_before_start = true

 

  # Optional
  # trigger_schedule = "cron(0 1 * * ? *)"

 

  glue_job_arguments = {
    "--source"                   = "kafka"
    "--source_kafka_endpoint"    = local.kafka_bootstrap_endpoint[local.env]
    "--source_kafka_secret_name" = "<secret-name>"
    "--source_kafka_topic"       = "<topic>"

 

    "--transformer1"              = "timestamp"
    "--transformer1_column"       = "processing_timestamp"
    "--transformer1_value_format" = "json"

 

    "--transformer2"                 = "kafka_unpack"
    "--transformer2_metadata_column" = "__metadata__"

 

    "--sink_transformer1"                          = "kafka_split"
    "--sink_transformer1_schema_registry_endpoint" = local.schema_registry_endpoint[local.env]
    "--sink_transformer1_secret_name"              = "<secret-name>"

 

    "--sink"                             = "iceberg"
    "--sink_iceberg_catalog_type"        = "glue"
    "--sink_iceberg_catalog_id"          = local.miw_account_id[local.env]
    "--sink_iceberg_database"            = "<glue-db>"
    "--sink_iceberg_warehouse"           = "<s3-warehouse>"
    "--sink_iceberg_checkpoint_dir"      = "<s3-checkpoint-dir>"
    "--sink_iceberg_assume_role_arn"     = "<assume-role-arn>"
    "--sink_iceberg_assume_session_name" = "mif-glue-iceberg"

 

    "--sink_trigger" = "availableNow"
  }
}
```