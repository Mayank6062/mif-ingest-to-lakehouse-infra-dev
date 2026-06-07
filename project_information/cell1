```
Analyze this repository and create Repository Discovery Documentation.

Focus on:

1. Executive Summary
   - Repository Name
   - Purpose
   - Business Objective
   - System Objective

2. Business Flow
   - Upstream Systems
   - Downstream Systems
   - Dependencies
   - High Level Workflow

3. Architecture Analysis
   - System Architecture
   - Component Architecture
   - Integration Architecture

4. Repository Structure
   - Folder Tree
   - Folder Responsibilities
   - Important Files

5. File Inventory
   - File Name
   - Purpose
   - Dependencies

Generate detailed markdown documentation.

Do not generate code.
```

# Repository Discovery Documentation
## MIF Ingest to Lakehouse Infrastructure - Development Environment
 
---
 
## 1. Executive Summary
 
### Repository Name
**mif-ingest-to-lakehouse-infra-dev**
 
### Purpose
Infrastructure-as-Code (IaC) repository that manages the deployment and orchestration of data ingestion jobs in a development environment. The repository uses Terraform to define and provision AWS Glue jobs integrated with the Talaria data ingestion framework, enabling automated data movement from multiple upstream source systems into a centralized lakehouse.
 
### Business Objective
- **Enable Data Integration**: Provide a scalable, maintainable platform for ingesting structured data from 50+ enterprise source systems
- **Reduce Manual Integration Effort**: Automate ingestion pipeline creation and deployment through IaC patterns
- **Support Business Analytics**: Feed the centralized data lakehouse with clean, consistent data to enable business intelligence, reporting, and data-driven decision-making
- **Maintain Data Governance**: Standardize data ingestion patterns across all source systems while maintaining proper access control and compliance
 
### System Objective
- **Infrastructure Provisioning**: Automatically create and manage AWS Glue jobs with proper IAM roles and network configurations
- **Pipeline Orchestration**: Orchestrate data flow from source systems through Talaria transformations into Iceberg-formatted data lakes
- **Consistent Patterns**: Enforce standardized Terraform module usage across all ingestion jobs to reduce complexity and maintenance burden
- **CI/CD Automation**: Integrate with Vela CI/CD platform to automatically test and deploy infrastructure changes per source system
- **Data Quality**: Support multiple transformation strategies (timestamp, Kafka unpacking, schema registry integration, etc.) to ensure data quality at ingestion point
 
---
 
## 2. Business Flow
 
### Upstream Systems
 
#### Enterprise Resource Planning (ERP) Systems
- **SAP Systems**: SAP ABAP tables (SAP TC1/TC2/TCA/TCC/TCD/TCE/TCF/TCG/TCL), SAP RM modules
- **Oracle Systems**: JD Edwards One World (JDE E1), JDW (JD Edwards World)
- **Other ERP**: Axapta (now Dynamics 365), Concur (expense management), Exact, Yongyou, Kingdee
 
#### Commodity Trading Systems
- **AGTR Systems**: APAC Qilin, TDA Americas, TDA APAC Cocoa, TDA Cocoa, TDA Grains, TDA Quant, TDA Vegoils, WTG Seaborne
- **Magellan Platform**: Multiple modules (Market, Trade, Weather, Quotes, GIS, etc.)
- **Trading Platforms**: Findur, FinCAD (FPS), Trading Tracker, Trust (CTMS platforms)
 
#### Financial Systems
- **Aurora**: Inbound billing and invoice management system with Kafka streaming support
- **Concur**: Travel and expense management
- **OneStream**: Financial planning and analysis
 
#### Operational Systems
- **Supply Chain**: LIMS, Costko, IIQ (Integrated Inventory)
- **Procurement**: Opentext (document management)
- **Business Tools**: Iamadmin portal, reference data systems (GTC Reference Data)
 
#### Data Lakes & External Sources
- **OpenMeteo**: Weather and meteorological data
- **Kafka Topics**: Real-time event streams (Aurora inbound, CTMS streaming, etc.)
 
### Downstream Systems
 
#### Primary Destination: Data Lakehouse
- **Iceberg Format Data Lakes** organized by source system
- **Database Structure**: `lh_<source_system>_report_raw_<environment>`
  - Example: `lh_agtr_apac_qilin_report_raw_dev`
  - Example: `lh_cmmp_report_raw_dev`
 
#### Data Consumers
1. **Analytics & BI Teams**: Consuming data for reporting and analysis
2. **Data Scientists**: Using data for model development and experimentation
3. **Business Users**: Accessing curated datasets through BI tools
4. **Compliance & Audit**: Monitoring and validating ingestion processes
 
### Dependencies
 
#### External Service Dependencies
- **AWS Services**:
  - Glue Jobs (ETL execution)
  - S3 (data storage)
  - IAM (authentication and authorization)
  - Secrets Manager (credential management)
  - Lambda (job scheduling and restart triggers)
  - EventBridge (job scheduling triggers)
  - CloudWatch (logging and monitoring)
 
- **Talaria Framework**: v0.3.3 (data transformation and ingestion engine)
- **Schema Registry**: For Kafka topic schema validation and compatibility
 
- **External Systems**:
  - Source system databases (direct JDBC connections or file exports)
  - Kafka brokers (for streaming data sources)
  - Secret management systems (storing database credentials)
 
#### Internal Dependencies
- **Terraform Modules**: `minerva-talaria-terraform-modules` (from git::https://git.cglcloud.com)
  - `talaria-staging2iceberg` module for standardized ingestion pipelines
  - Provides standard Glue job configurations and IAM role templates
 
- **MIF Framework**: Core transformation and ingestion logic
- **Talaria Restarter**: Manages job retries and failure handling (referenced in aws-infra-minerva-mif-dev)
 
### High Level Workflow
 
#### Data Ingestion Pipeline Flow
 
```
SOURCE SYSTEMS (ERP, Operational, Streaming)
            ↓
            │
    ┌───────┴──────────┐
    │                  │
[JDBC Ingestion]    [Kafka Streaming]
    │                  │
    └───────┬──────────┘
            ↓
    AWS GLUE JOB (Talaria)
    ├─ Source Configuration (Database/Kafka/File)
    ├─ Transformations (Timestamp, Schema validation, Unpacking)
    ├─ Data Validation & Quality Checks
    └─ Sink Configuration (Iceberg)
            ↓
    AWS S3 + Iceberg Metadata
            ↓
    LAKEHOUSE DATABASE
    lh_<source>_report_raw_<env>
            ↓
    ANALYTICS & BUSINESS CONSUMERS
```
 
#### Execution Process for Each Ingestion Job
1. **Trigger**: Event from EventBridge scheduler or manual trigger
2. **Glue Job Startup**: AWS Glue provisions workers and executes Python script
3. **Source Connection**: Establishes connectivity to source system
   - JDBC: Direct database connection
   - Kafka: Consumer connection with authentication
   - File: S3/HTTP retrieval
4. **Data Extract**: Retrieves data according to configured strategy
   - Full extract or incremental based on configuration
5. **Transformations**: Applies Talaria transformations:
   - Timestamp normalization
   - Schema validation against registry
   - Data unpacking (JSON/Kafka payloads)
   - Data type conversions
6. **Data Load**: Writes to Iceberg table in S3
7. **Metadata Update**: Updates Glue Data Catalog with new table metadata
8. **Monitoring**: Sends execution metrics to Datadog and CloudWatch
 
#### Data Flow Example: AGTR APAC Qilin System
```
AGTR Qilin ERP (Source)
    ↓
[JDBC Connection via Talaria]
    ├─ Subdir Scanner Strategy
    ├─ Timestamp Transformer
    ├─ Schema Validation
    ↓
AWS Glue Job: talaria-0.3.3
    ├─ Database Role: agtr_apac_dev_procintegratedingestionengineer
    ├─ Glue Role: dev-mif-agtr-apac-glue-role
    ↓
S3 Bucket: dev-lh1-agtr-src
    ↓
Iceberg Lake: lh_agtr_apac_qilin_report_raw_dev
    ↓
Analytics & Reporting
```
 
---
 
## 3. Architecture Analysis
 
### System Architecture
 
#### High-Level Data Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                   MINERVA DATA PLATFORM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SOURCE SYSTEMS LAYER                                    │  │
│  │  ├─ ERP Systems (SAP, JDE, Axapta, etc.)                │  │
│  │  ├─ Commodity Trading Systems (AGTR, Magellan, etc.)   │  │
│  │  ├─ Financial Systems (Aurora, OneStream, etc.)        │  │
│  │  ├─ Operational Systems (Supply Chain, Procurement)    │  │
│  │  └─ External Data Sources (OpenMeteo, Kafka)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  INTEGRATION LAYER (MIF - Minerva Ingestion Framework)  │  │
│  │  ├─ Talaria v0.3.3 (Transformation Engine)              │  │
│  │  ├─ AWS Glue Jobs (ETL Orchestration)                   │  │
│  │  ├─ JDBC Connectors (Batch Ingestion)                   │  │
│  │  ├─ Kafka Consumers (Stream Ingestion)                  │  │
│  │  └─ Schema Registry (Data Validation)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  STORAGE LAYER (AWS)                                     │  │
│  │  ├─ S3 Buckets (dev-lh1-<source>-src)                    │  │
│  │  ├─ Iceberg Tables (Columnar Format)                     │  │
│  │  └─ Glue Data Catalog (Metadata)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LAKEHOUSE LAYER                                         │  │
│  │  ├─ Database Schemas (lh_<source>_report_raw_dev)       │  │
│  │  ├─ Raw Data Tables (Ingested Data)                     │  │
│  │  └─ Metadata (Source, Timestamp, etc.)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CONSUMPTION LAYER                                       │  │
│  │  ├─ Analytics & BI Tools                                │  │
│  │  ├─ Data Science Platforms                              │  │
│  │  └─ Business Intelligence Dashboards                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```
 
#### AWS Infrastructure Architecture
```
┌────────────────────────────────────────────────────────────────┐
│                    AWS Account (242201267815)                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ COMPUTE LAYER                                           │ │
│  │ ┌─────────────────────────────────────────────────────┐ │ │
│  │ │ AWS Glue Jobs (50+ instances, one per source)      │ │ │
│  │ │ ├─ Execution Role: <source>-dev-mif-glue-role     │ │ │
│  │ │ ├─ Python Version: 3.x                             │ │ │
│  │ │ ├─ Glue Version: 5.1+                              │ │ │
│  │ │ ├─ Workers: G.2X (configurable)                    │ │ │
│  │ │ └─ Max Concurrent Runs: Queued                     │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  │ ┌─────────────────────────────────────────────────────┐ │ │
│  │ │ Lambda Functions                                    │ │ │
│  │ │ ├─ Job Restart Handler                             │ │ │
│  │ │ ├─ Job Scheduler                                   │ │ │
│  │ │ └─ Health Check Monitors                           │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ STORAGE LAYER                                           │ │
│  │ ┌─────────────────────────────────────────────────────┐ │ │
│  │ │ S3 Data Buckets                                     │ │ │
│  │ │ ├─ dev-lh1-agtr-src (AGTR sources)                 │ │ │
│  │ │ ├─ dev-lh1-cmmp-src (CMMP sources)                 │ │ │
│  │ │ ├─ dev-lh1-<system>-src (per source)               │ │ │
│  │ │ └─ Path: s3://bucket/source_system/table_name/     │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  │ ┌─────────────────────────────────────────────────────┐ │ │
│  │ │ Glue Data Catalog                                   │ │ │
│  │ │ ├─ Databases: lh_<source>_report_raw_dev           │ │ │
│  │ │ ├─ Tables: Iceberg format metadata                 │ │ │
│  │ │ └─ Classifications, Connections, Security          │ │ │
│  │ └─────────────────────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
│                         ↓                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ INTEGRATION & ORCHESTRATION                             │ │
│  │ ├─ EventBridge Rules (Schedule triggers)              │ │
│  │ ├─ Secrets Manager (Credential storage)               │ │
│  │ ├─ IAM Roles & Policies (Access control)              │ │
│  │ └─ VPC/Connections (Network connectivity)             │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ MONITORING & LOGGING                                    │ │
│  │ ├─ CloudWatch Logs (Glue job output)                   │ │
│  │ ├─ CloudWatch Metrics (Job duration, records, etc.)    │ │
│  │ └─ Datadog Integration (dd_api_key secret)             │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```
 
### Component Architecture
 
#### AWS Glue Job Component (Core Ingestion Unit)
```
┌────────────────────────────────────────────────────────────────┐
│                  AWS GLUE JOB COMPONENT                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Input & Configuration                                         │
│  ├─ Job Name: talaria-<source>-<type>                         │
│  ├─ Glue Version: 5.1                                         │
│  ├─ Python Version: 3.x                                       │
│  ├─ Worker Type: G.2X (2 vCPU, 16 GB RAM per worker)          │
│  ├─ Number of Workers: 2-10 (configurable)                    │
│  ├─ Execution Class: FLEX (for cost optimization)             │
│  └─ Max Concurrent Runs: Queued (only 1 active at a time)     │
│                                                                │
│  Execution Environment                                         │
│  ├─ IAM Execution Role (with S3, Glue, Secrets permissions)   │
│  ├─ VPC Connections (if on-premises connectivity needed)      │
│  ├─ Security Groups (network isolation)                       │
│  └─ Additional Python Modules:                                │
│      ├─ avro==1.12.0 (serialization)                          │
│      ├─ retry (error handling)                                │
│      ├─ requests (HTTP calls)                                 │
│      ├─ jsonschema (schema validation)                        │
│      ├─ pyiceberg (Iceberg integration)                       │
│      └─ pyyaml (configuration parsing)                        │
│                                                                │
│  Data Processing Pipeline                                      │
│  ├─ Source Connector                                           │
│  │  ├─ JDBC Connection (Database extract)                     │
│  │  ├─ Kafka Consumer (Stream ingestion)                      │
│  │  └─ File Reader (S3/HTTP sources)                          │
│  │                                                             │
│  ├─ Talaria Transformers (Configurable Chain)                │
│  │  ├─ timestamp: Add/normalize processing timestamp          │
│  │  ├─ kafka_unpack: Extract from Kafka JSON payloads        │
│  │  ├─ kafka_split: Partition messages by schema             │
│  │  ├─ schema_registry: Validate against registry            │
│  │  └─ Custom transformers (as needed)                        │
│  │                                                             │
│  ├─ Sink Connector                                             │
│  │  ├─ Iceberg Writer (Columnar format)                       │
│  │  ├─ Partitioning Strategy                                  │
│  │  └─ Schema Evolution Handling                              │
│  │                                                             │
│  └─ Error Handling & Monitoring                                │
│     ├─ Retry Logic (via talaria-restarter)                    │
│     ├─ CloudWatch Metrics (records, duration, errors)        │
│     ├─ Datadog Integration (external monitoring)              │
│     └─ Failed Job Alerts                                      │
│                                                                │
│  Output                                                         │
│  ├─ S3 Iceberg Files (s3://bucket/database/table/)            │
│  ├─ Glue Data Catalog Metadata Update                         │
│  └─ Job Execution Logs                                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```
 
#### Terraform Module Pattern (glue_job module)
```
┌────────────────────────────────────────────────────────────────┐
│          TERRAFORM MODULE: glue_job                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Module Inputs (Variables)                                     │
│  ├─ glue_version: AWS Glue version (e.g., "5.1")             │
│  ├─ worker_type: Worker specification (G.2X, G.4X, etc.)     │
│  ├─ number_of_workers: Number of workers per job             │
│  ├─ execution_class: FLEX or STANDARD                         │
│  ├─ max_concurrent_runs: Queuing behavior                     │
│  ├─ glue_job_arguments: Custom job parameters                │
│  ├─ job_version: Talaria version                              │
│  ├─ job_type: unified, stream, batch                          │
│  ├─ tags: Resource tags (Name, Script, Environment)          │
│  └─ start_job_on_change: Auto-trigger on deploy              │
│                                                                │
│  Resources Created                                             │
│  ├─ aws_glue_job: Main Glue job resource                      │
│  ├─ aws_lambda_invocation: Job trigger (conditional)         │
│  ├─ IAM Role: Execution permissions                           │
│  ├─ Glue Connection: Database/Kafka connectivity              │
│  └─ CloudWatch Resources: Logging & metrics                   │
│                                                                │
│  Module Outputs                                                │
│  ├─ glue_job_arn: Job ARN reference                           │
│  ├─ glue_job_name: Job name for reference                     │
│  └─ glue_job_role_arn: IAM role ARN                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```
 
### Integration Architecture
 
#### CI/CD Integration (Vela Pipeline)
```
┌────────────────────────────────────────────────────────────────┐
│                  VELA CI/CD PIPELINE FLOW                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Trigger Events                                                │
│  ├─ Pull Request (on branch: main)                            │
│  ├─ Push to main Branch                                       │
│  └─ File Change Detection (per source folder)                 │
│                                                                │
│  Stage 1: LINT (All PRs to main)                              │
│  ├─ check_vela: Validate folder structure                     │
│  ├─ check_vela_yaml: Validate .vela.yml syntax                │
│  │   └─ Generated from .vela.py via check_vela_yaml.py       │
│  └─ lint: Run pre-commit hooks                                │
│      ├─ Terraform fmt validation                              │
│      ├─ Terraform validate                                    │
│      ├─ terraform-docs generation                             │
│      └─ YAML/JSON linting                                     │
│                                                                │
│  Stage 2: TERRAFORM PER FOLDER (if files changed)            │
│  │                                                             │
│  ├─ For each source folder in FOLDERS list:                   │
│  │  ├─ generate_aws: Get AWS credentials via OIDC            │
│  │  │   └─ Role: OIDCVelaMinervaForManagingIngestingToLake   │
│  │  │                                                        │
│  │  ├─ terraform_init: terraform init                        │
│  │  │   └─ Backend: S3 state (centralized)                   │
│  │  │                                                        │
│  │  ├─ terraform_plan: terraform plan (on PR)                │
│  │  │   ├─ Format: -json for parsing                         │
│  │  │   └─ Output: PR comment with plan details              │
│  │  │                                                        │
│  │  └─ terraform_apply: terraform apply (on merge to main)   │
│  │      └─ Auto-approve: -auto-approve flag                  │
│  │                                                             │
│  │  Note: Only runs if files in folder/<path>/* changed      │
│  │                                                             │
│  └─ (Repeats for all 50+ source folders)                     │
│                                                                │
│  Stage 3: RESTART_JOB                                         │
│  └─ Runs restart_job.sh for failed/updated jobs              │
│                                                                │
│  Stage 4: SCHEDULE_JOB                                        │
│  └─ Updates EventBridge schedule rules for job triggers      │
│                                                                │
│  Stage 5: MONITORING_SUMMARY                                  │
│  └─ Generate execution summary & send to Datadog             │
│     ├─ Success/failure counts                                │
│     ├─ Plan changes summary                                  │
│     └─ Duration metrics                                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```
 
#### Source System to Lakehouse Integration Pattern
 
**Example: AGTR APAC Qilin System**
```
┌─────────────────────────────────────────────────────────────┐
│ UPSTREAM: AGTR APAC Qilin ERP                              │
│ (Database/Files on-premises)                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│ INTEGRATION: Terraform Module Instance                      │
│ module "agtr_apac_qilin_staging_ingestion"                 │
│                                                             │
│ Configuration:                                              │
│ ├─ source_system: "agtr_apac_qilin"                        │
│ ├─ environment: "dev"                                      │
│ ├─ talaria_version: "0.3.3"                                │
│ ├─ scanner_strategy: "subdir"                              │
│ ├─ roles:                                                  │
│ │  ├─ Lakehouse Role: agtr_apac_dev_procintegratedingestion
│ │  └─ MIF Glue Role: dev-mif-agtr-apac-glue-role          │
│ └─ storage:                                                │
│    ├─ S3 Bucket: dev-lh1-agtr-src                         │
│    └─ Database: lh_agtr_apac_qilin_report_raw_dev          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│ AWS GLUE JOB: talaria-agtr-apac-qilin                       │
│                                                             │
│ Execution Details:                                          │
│ ├─ Trigger: EventBridge schedule (daily/custom)            │
│ ├─ Processing:                                             │
│ │  ├─ JDBC Connect → AGTR Database                        │
│ │  ├─ Extract data via subdir scanner                      │
│ │  ├─ Apply timestamp transformation                       │
│ │  └─ Validate schema consistency                          │
│ ├─ Output:                                                 │
│ │  ├─ S3: s3://dev-lh1-agtr-src/agtr/qilin/<table>/       │
│ │  └─ Format: Iceberg (Parquet-based)                      │
│ └─ Monitoring:                                             │
│    ├─ CloudWatch Logs & Metrics                            │
│    └─ Datadog Integration                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│ DOWNSTREAM: Data Lakehouse                                  │
│                                                             │
│ Database: lh_agtr_apac_qilin_report_raw_dev                │
│ ├─ Tables: <table_name> (per AGTR entity)                  │
│ │  ├─ Columns: (derived from source + metadata)            │
│ │  └─ Format: Iceberg (versioned, time-travel capable)     │
│ ├─ Metadata: Source info, timing, quality metrics          │
│ └─ Access:                                                 │
│    └─ Via Glue Data Catalog + Athena/Spectrum              │
└──────────────────────────────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│ CONSUMERS: Analytics, BI, Data Science                      │
└──────────────────────────────────────────────────────────────┘
```
 
---
 
## 4. Repository Structure
 
### Folder Tree & Organization
 
```
mif-ingest-to-lakehouse-infra-dev/
│
├── SOURCE_SYSTEM_FOLDERS/             [~50 folders representing upstream systems]
│   ├── agtr-*/                        [Agricultural Trading Systems]
│   │   ├── agtr-apac-qilin/
│   │   ├── agtr-tda-americas/
│   │   ├── agtr-tda-apac-cocoa/
│   │   ├── agtr-tda-cocoa/
│   │   ├── agtr-tda-grains/
│   │   ├── agtr-tda-quant/
│   │   ├── agtr-tda-vegoils/
│   │   └── agtr-wtg-seaborne/
│   │
│   ├── axapta/                        [ERP Systems]
│   ├── jdee1/
│   ├── jdw/
│   ├── m3/
│   ├── neolait-erp/
│   ├── saprm/
│   ├── saptc1/, saptc2/, saptca/, etc. [SAP Systems]
│   ├── yongyou/
│   │
│   ├── aurora/                        [Streaming & Real-time Systems]
│   ├── cmmp/
│   ├── cnc/
│   ├── cocoa-minderest/
│   │
│   ├── concur/                        [Financial & Operational Systems]
│   ├── customer-hierarchy/
│   ├── egtps/
│   ├── exact/
│   ├── fts/
│   ├── genetec/
│   ├── iiq/
│   ├── onestream/
│   ├── sfsc/
│   │
│   ├── jdbc_batch/                    [Special: Batch ingestion jobs]
│   │   ├── glue_ingest_*.tf           [Individual job definitions]
│   │   ├── modules/                   [JDBC-specific modules]
│   │   │   ├── jdbc_notification_targets/
│   │   │   ├── jdbc_source/
│   │   │   ├── jdbc_source_table/
│   │   │   ├── jdbc_target/
│   │   │   └── jdbc_target_table/
│   │   ├── drivers/                   [Database drivers]
│   │   ├── locals.tf                  [Configuration]
│   │   ├── secrets.tf
│   │   └── get_latest_talaria.py      [Utility script]
│   │
│   ├── mif_tests/                     [Testing & Integration Tests]
│   └── integration_tests/
│
├── INFRASTRUCTURE & FRAMEWORK/
│   ├── modules/                       [Reusable Terraform Modules]
│   │   └── glue_job/                  [Core Glue Job Module]
│   │       ├── data.tf                [Data sources]
│   │       ├── data_models.tf         [Data structures]
│   │       ├── glue.tf                [Glue job resource]
│   │       ├── iam.tf                 [IAM roles & policies]
│   │       ├── locals.tf              [Local variables]
│   │       ├── registry.tf            [Schema registry config]
│   │       ├── variables.tf           [Input variables]
│   │       ├── cron_trigger.tf        [EventBridge scheduling]
│   │       └── README.md              [Module documentation]
│   │
│   └── .ci/                           [CI/CD Configuration]
│       ├── check_vela_yaml.py         [YAML validation/generation]
│       ├── ensure_folders.py          [Folder structure validation]
│       └── common-files/              [Shared pipeline files]
│
├── REPOSITORY METADATA/
│   ├── .vela.py                       [Vela pipeline (Starlark)]
│   ├── .vela.yml                      [Vela pipeline (YAML, auto-generated)]
│   ├── .terraform-docs.yml            [Terraform docs config]
│   ├── .pre-commit-config.yaml        [Pre-commit hooks]
│   ├── .gitignore                     [Git ignore rules]
│   ├── CODEOWNERS                     [Code ownership]
│   ├── README.md                      [Main documentation]
│   └── REPOSITORY_DISCOVERY_DOCUMENTATION.md [This file]
│
├── SCRIPTS & UTILITIES/
│   ├── scripts/
│   │   └── restart_job.sh             [Job restart script]
│   │
│   ├── .utils/                        [Utility modules]
│   └── .ensure_folders.py             [Folder validation]
│
└── GIT & VERSION CONTROL/
    ├── .git/                          [Git repository]
    └── .gitignore
```
 
### Folder Responsibilities
 
#### Source System Folders (50+ directories)
 
**Pattern & Naming Convention:**
- Folder name matches source system identifier
- Can be organized by business domain (ag-tr, sap, egtps, etc.)
 
**Standard Contents per Source:**
```
<source_system>/
├── locals.tf          [REQUIRED] Environment & metadata variables
│                      └─ ent_func: Enterprise function code
│                      └─ subgroup: Business unit identifier
│                      └─ glue_jobs: Job definitions (if multiple)
│
├── main.tf            [TYPICAL] Terraform module instantiation
│   OR glue.tf         [ALTERNATIVE] Direct Glue job definition
│
├── *.tf               [OPTIONAL] Additional resource definitions
│   ├─ secrets.tf      [Credential management]
│   ├─ iam.tf          [IAM role customization]
│   ├─ connections.tf  [VPC/network setup]
│   └─ variables.tf    [Input variables]
│
├── modules/           [OPTIONAL] Source-specific modules
│   ├─ glue_job/       [If reusing across multiple jobs]
│   └─ transformers/   [Custom transformation modules]
│
└── README.md          [OPTIONAL] Source-specific documentation
```
 
**Responsibilities:**
- Define data ingestion configuration for their source system
- Manage IAM roles and security policies for their system
- Configure Glue job parameters (workers, timeouts, transformers)
- Handle source-specific credentials and connections
- Document system-specific requirements and quirks
 
#### Specialization Folders
 
**jdbc_batch/ - Batch Ingestion Hub**
- Purpose: Central location for large batch ingestion jobs
- Contains 100+ individual Glue job definitions (glue_ingest_*.tf)
- Manages JDBC connectors for database-to-lakehouse ETL
- Custom modules for complex batch scenarios
- Drivers folder for database-specific connector libraries
 
**aurora/ - Streaming Architecture Hub**
- Purpose: Kafka/streaming ingestion for real-time data
- Handles Aurora inbound billing system with 24/7 streaming
- Implements Kafka consumer groups and offset management
- Manages schema registry integration for validation
 
**mif_tests/ & integration_tests/**
- Purpose: Test and validate ingestion pipelines
- Contains sample job definitions and test fixtures
- Validates end-to-end data flow
- Tests transformation logic and error handling
 
#### modules/ - Terraform Module Library
 
**glue_job/ Module** (Primary, Reusable Module)
- Purpose: Standardized Glue job creation and configuration
- Handles all AWS Glue job resource management
- Provides IAM role templates and best practices
- Manages CloudWatch logging and metrics
- Supports multiple job types (batch, streaming, unified)
- Includes EventBridge scheduling integration
- Supports Lambda-based job restart triggers
 
**Responsibilities of glue_job module:**
- Abstract AWS Glue complexity into simple variables
- Enforce consistent job configuration across sources
- Manage IAM permissions through role templates
- Handle datalake format (Iceberg) configuration
- Support schema registry integration
- Provide monitoring and alerting setup
 
#### .ci/ - CI/CD Infrastructure
 
**check_vela_yaml.py**
- Validates Vela pipeline YAML syntax
- Can auto-generate .vela.yml from .vela.py (Starlark)
- Ensures pipeline consistency across all environments
 
**ensure_folders.py**
- Validates repository folder structure against FOLDERS list
- Ensures all folders follow naming conventions
- Prevents orphaned or misnamed directories
- Runs during linting phase of CI/CD
 
**common-files/**
- Shared resources used across pipeline stages
- Common build scripts and utilities
- Standardized deployment templates
 
#### scripts/ - Automation Utilities
 
**restart_job.sh**
- Restarts failed Glue jobs manually
- Used in post-deployment validation
- Supports batch restart of multiple jobs
- Part of job recovery automation
 
### Important Files
 
| File | Purpose | Owner | Frequency |
|------|---------|-------|-----------|
| `.vela.py` | Pipeline definition (Starlark) | Ingest Framework Team | Updated per pipeline changes |
| `.vela.yml` | Pipeline definition (YAML, auto-generated from .vela.py) | Ingest Framework Team | Auto-generated |
| `CODEOWNERS` | Code ownership & review requirements | Ingest Framework Team | Updated per team changes |
| `.pre-commit-config.yaml` | Pre-commit hook configuration | Ingest Framework Team | Updated per linting requirements |
| `.terraform-docs.yml` | Terraform documentation settings | Ingest Framework Team | Rarely changed |
| `modules/glue_job/variables.tf` | Core module input specification | Ingest Framework Team | Updated per feature requests |
| `modules/glue_job/glue.tf` | Glue job resource implementation | Ingest Framework Team | Updated for AWS updates |
| `README.md` | Primary repository documentation | Ingest Framework Team | Updated per feature releases |
| `<source>/locals.tf` | Source system configuration | Source system owner | Updated per environment changes |
| `<source>/main.tf` | Source system ingestion definition | Source system owner | Updated per job changes |
| `.ci/check_vela_yaml.py` | Pipeline validation script | Ingest Framework Team | Updated per CI/CD changes |
| `.ci/ensure_folders.py` | Folder structure validation | Ingest Framework Team | Updated per folder additions |
| `scripts/restart_job.sh` | Job recovery automation | Platform team | Updated per recovery logic changes |
 
---
 
## 5. File Inventory
 
### File Name Convention System
 
The repository follows consistent naming patterns for easy identification:
 
**Terraform Files by Purpose:**
- `locals.tf` - Local variable definitions (per source)
- `main.tf` - Main Terraform module instantiation (per source)
- `glue.tf` - Direct Glue resource definitions (alternative to main.tf)
- `secrets.tf` - Secret/credential management
- `iam.tf` - IAM roles and policies
- `connections.tf` - VPC/network connections
- `variables.tf` - Input variable declarations
- `data.tf` - Data source definitions
- `registry.tf` - Schema registry integration
 
**Glue Job Definition Files (jdbc_batch/ specific):**
- `glue_ingest_<system>.tf` - Job definition per source system
  - Example: `glue_ingest_axapta.tf`, `glue_ingest_findur.tf`
  - Naming: glue_ingest_<system_name>.tf (lowercase, underscores)
 
**CI/CD & Configuration:**
- `.vela.py` - Vela pipeline (Starlark, human-editable)
- `.vela.yml` - Vela pipeline (YAML, auto-generated)
- `.pre-commit-config.yaml` - Pre-commit hooks
- `.terraform-docs.yml` - Terraform docs config
- `.gitignore` - Git ignore rules
- `CODEOWNERS` - Code ownership
 
**Utility & Support Files:**
- `README.md` - Main documentation
- `*.md` - Documentation files (per module/folder)
- `.ci/check_vela_yaml.py` - YAML validation
- `.ci/ensure_folders.py` - Folder validation
- `scripts/restart_job.sh` - Bash utilities
- `get_latest_talaria.py` - Version management
- `*.py` - Python utility scripts
 
### File Purpose Matrix
 
#### Core Infrastructure Files
 
| File Path | Purpose | Key Responsibilities | Dependencies |
|-----------|---------|---------------------|--------------|
| `modules/glue_job/glue.tf` | AWS Glue job resource definition | Create & configure Glue jobs, set workers, configure job arguments | IAM roles, Glue version settings |
| `modules/glue_job/iam.tf` | IAM role template for Glue jobs | Define job execution role, policies for S3/Glue/Secrets access | AWS IAM, source system requirements |
| `modules/glue_job/cron_trigger.tf` | EventBridge scheduler integration | Schedule job triggers, set recurrence patterns | EventBridge service, Lambda functions |
| `modules/glue_job/variables.tf` | Module input specification | Define configurable parameters for all Glue jobs | Terraform variable syntax |
| `modules/glue_job/locals.tf` | Local variables & computed values | Calculate derived values, format strings | Module variables |
| `modules/glue_job/data.tf` | Data sources for lookups | Fetch runtime values (AMI, subnets, etc.) | AWS Data sources |
| `modules/glue_job/registry.tf` | Schema registry configuration | Integrate with schema registry for validation | Schema registry endpoints |
 
#### Source System Configuration Files
 
| File Path | Purpose | Key Responsibilities | Dependencies |
|-----------|---------|---------------------|--------------|
| `<source>/locals.tf` | Environment & source variables | Define ent_func, subgroup, job parameters | Source system attributes |
| `<source>/main.tf` | Module instantiation | Call glue_job module with source-specific config | modules/glue_job, source locals |
| `<source>/glue.tf` | Alternative job definition | Direct Glue resource for simple cases | AWS provider, IAM roles |
| `<source>/secrets.tf` | Credential management | Reference Secrets Manager secrets | AWS Secrets Manager |
| `<source>/iam.tf` | Custom IAM policies | Define source-specific permissions | AWS IAM, job requirements |
| `<source>/connections.tf` | Network connectivity | Configure VPC connections for on-prem access | VPC, security groups |
 
#### CI/CD & Pipeline Files
 
| File Path | Purpose | Key Responsibilities | Dependencies |
|-----------|---------|---------------------|--------------|
| `.vela.py` | Pipeline orchestration (Starlark) | Define stages, secrets, folder iteration logic | Vela CI/CD, folder list |
| `.vela.yml` | Generated pipeline (YAML) | Execute pipeline stages in sequence | .vela.py, Vela service |
| `.ci/check_vela_yaml.py` | YAML generation & validation | Convert Starlark to YAML, validate syntax | pyyaml, Starlark files |
| `.ci/ensure_folders.py` | Folder structure validation | Verify all folders match FOLDERS list | Folder list in code |
| `.pre-commit-config.yaml` | Pre-commit hook config | Run linting, formatting, docs generation | terraform, pre-commit framework |
 
#### Documentation & Metadata
 
| File Path | Purpose | Key Responsibilities | Dependencies |
|-----------|---------|---------------------|--------------|
| `README.md` | Main repository documentation | Overview, setup, deployment process | Markdown, repository structure |
| `CODEOWNERS` | Code ownership & review rules | Assign approvers per file/folder | GitHub CODEOWNERS format |
| `.terraform-docs.yml` | Terraform doc generation config | Configure markdown documentation output | terraform-docs tool |
| `modules/glue_job/README.md` | Module-specific documentation | Usage examples, input/output specs | Terraform doc format |
 
#### Utility & Support Files
 
| File Path | Purpose | Key Responsibilities | Dependencies |
|-----------|---------|---------------------|--------------|
| `scripts/restart_job.sh` | Job restart automation | Recover from job failures, manual restarts | AWS CLI, Glue service |
| `jdbc_batch/get_latest_talaria.py` | Version determination | Fetch latest Talaria version available | GitHub/registry API |
| `jdbc_batch/get_latest_talaria_lamba_and_schedule.xtf` | Lambda config | Configure Lambda for version fetching | AWS Lambda, scheduler |
| `jdbc_batch/modules/jdbc_source/` | JDBC source module | Handle database connectivity specifics | Database drivers |
 
### File Dependencies Map
 
```
DEPENDENCY HIERARCHY:
═══════════════════════
 
LEVEL 1: Foundation (AWS)
    └─ AWS Provider Configuration
       └─ IAM, S3, Glue, Secrets Manager, EventBridge
 
LEVEL 2: Core Modules
    ├─ modules/glue_job/
    │   ├─ glue.tf (Glue job resource)
    │   ├─ iam.tf (Execution roles)
    │   ├─ cron_trigger.tf (Job scheduling)
    │   ├─ variables.tf (Input spec)
    │   ├─ locals.tf (Local values)
    │   ├─ data.tf (Data sources)
    │   └─ registry.tf (Schema integration)
    │
    └─ modules/glue_job/README.md (Documentation)
 
LEVEL 3: Source System Configuration
    ├─ jdbc_batch/
    │   ├─ glue_ingest_*.tf (Job definitions)
    │   ├─ locals.tf (Configuration)
    │   ├─ modules/ (JDBC-specific)
    │   ├─ drivers/ (Database connectors)
    │   └─ secrets.tf (Credentials)
    │
    ├─ aurora/
    │   ├─ main.tf (Module call)
    │   ├─ locals.tf (Configuration)
    │   ├─ glue.tf (Job definition)
    │   └─ secrets.tf (Credentials)
    │
    ├─ <source-system>/
    │   ├─ main.tf → calls modules/glue_job/
    │   ├─ locals.tf → defines parameters
    │   ├─ secrets.tf → references secrets
    │   └─ iam.tf → custom policies
 
LEVEL 4: CI/CD & Automation
    ├─ .vela.py
    │   ├─ references: FOLDERS list (all source directories)
    │   ├─ calls: terraform_steps() per folder
    │   └─ generates: .vela.yml (auto)
    │
    ├─ .ci/check_vela_yaml.py
    │   ├─ reads: .vela.py
    │   ├─ generates: .vela.yml
    │   └─ validates: syntax
    │
    ├─ .ci/ensure_folders.py
    │   ├─ validates: folder existence
    │   └─ checks: naming conventions
    │
    ├─ .pre-commit-config.yaml
    │   ├─ runs: terraform fmt, validate
    │   ├─ runs: terraform-docs
    │   └─ runs: linting
 
LEVEL 5: Documentation & Metadata
    ├─ README.md
    ├─ CODEOWNERS
    ├─ .terraform-docs.yml
    └─ REPOSITORY_DISCOVERY_DOCUMENTATION.md
 
LEVEL 6: Utilities
    ├─ scripts/restart_job.sh
    ├─ jdbc_batch/get_latest_talaria.py
    └─ jdbc_batch/get_latest_talaria_lamba_and_schedule.xtf
```
 
### Cross-File Dependencies
 
**Critical Dependency Paths:**
 
1. **New Source System Deployment Path:**
   ```
   <new-source>/locals.tf (defines ent_func, subgroup)
        ↓
   <new-source>/main.tf (calls modules/glue_job)
        ↓
   modules/glue_job/*.tf (creates resources)
        ↓
   AWS IAM/Glue/S3 resources deployed
        ↓
   .vela.py (FOLDERS list) must include <new-source>
        ↓
   .ci/ensure_folders.py validates existence
        ↓
   Vela pipeline runs terraform for <new-source>
   ```
 
2. **Configuration Update Path:**
   ```
   <source>/locals.tf (modify ent_func, glue_jobs config)
        ↓
   .pre-commit-config.yaml (terraform fmt, validate runs)
        ↓
   Push to branch → .vela.yml runs
        ↓
   Vela generates AWS credentials (OIDC)
        ↓
   terraform plan → terraform apply
        ↓
   Glue job updated in AWS
   ```
 
3. **Pipeline Changes Path:**
   ```
   .vela.py (modify stages, folder list, secrets)
        ↓
   python .ci/check_vela_yaml.py --fix (regenerate YAML)
        ↓
   .pre-commit-config.yaml validates
        ↓
   .vela.yml updated (auto-generated)
        ↓
   Commit both .vela.py and .vela.yml
        ↓
   Vela reads .vela.yml for next run
   ```
 
---
 
## Summary
 
This **MIF Ingest to Lakehouse Infrastructure Repository** serves as the central Infrastructure-as-Code hub for the Minerva data platform's ingestion layer in the development environment. It orchestrates data movement from 50+ upstream enterprise systems through AWS Glue jobs powered by the Talaria transformation framework into an Apache Iceberg-based data lakehouse.
 
**Key Characteristics:**
- **Scale**: 50+ source system folders with 100+ individual Glue jobs
- **Architecture**: Modular Terraform with reusable glue_job component
- **Automation**: Vela CI/CD with per-folder change detection and deployment
- **Technology**: Terraform IaC, AWS Glue, Talaria transformations, Iceberg format
- **Governance**: Code ownership via CODEOWNERS, pre-commit validation, Datadog monitoring
- **Maintenance**: Clear folder organization, standardized file naming, documented dependencies
 
The repository is actively maintained by the Minerva Ingest Framework Team and IT department, with code reviews from domain-specific teams (AGTR, Commodities, Food, etc.).


Start the servers
Terminal 1 — Backend:
cd c:\Users\MayankSoni\Documents\poc\backend
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


Terminal 2 — Frontend:
$env:PATH = "C:\Program Files\nodejs;$env:APPDATA\npm;" + $env:PATH
cd c:\Users\MayankSoni\Documents\poc\frontend
npm run dev
Then open http://localhost:3000 in your browser.


Stop the servers
Option A — In the terminal (easiest):
Go to each terminal and press Ctrl + C

Option B — Kill by port (from any terminal):
Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess -Force
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force

One-command start (both at once)
$env:PATH = "C:\Program Files\nodejs;$env:APPDATA\npm;" + $env:PATH
cd c:\Users\MayankSoni\Documents\poc
.\start.ps1