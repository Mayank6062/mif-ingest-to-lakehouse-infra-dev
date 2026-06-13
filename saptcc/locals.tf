locals {
  ent_func = "AGTR"
  subgroup = "APAC"

  glue_jobs = {
  "kafka-to-iceberg-batch-saptcc-multi-1" = {
    job_type     = "unified"
    job_version  = "0.3.0"
    glue_version = "5.1"

    number_of_workers = 2
    worker_type       = "G.1X"
    stop_before_start = true

    glue_job_arguments = {
      "--source"                   = "kafka"
      "--source_kafka_endpoint"    = local.kafka_bootstrap_endpoint[local.env]
      "--source_kafka_secret_name" = "minerva-${local.env}-corp-mif-saptcc-gluejob-sa-cc-api-creds"
      "--source_kafka_topic"       = "${local.env}.saptcc.multi-1.raw"

      "--transformer1"              = "timestamp"
      "--transformer1_column"       = "processing_timestamp"
      "--transformer1_value_format" = "json"

      "--transformer2"                 = "kafka_unpack"
      "--transformer2_metadata_column" = "__metadata__"

      "--sink_transformer1"                          = "kafka_split"
      "--sink_transformer1_schema_registry_endpoint" = local.schema_registry_endpoint[local.env]
      "--sink_transformer1_secret_name"              = "minerva-${local.env}-corp-mif-saptcc-gluejob-sa-cc-api-creds"

      "--sink"                             = "iceberg"
      "--sink_iceberg_catalog_type"        = "glue"
      "--sink_iceberg_catalog_id"          = local.miw_account_id[local.env]
      "--sink_iceberg_database"            = "lh_sap_tcc_raw_dev"
      "--sink_iceberg_warehouse"           = "s3://minerva-dev-src-corp/current/prd/raw/sap_tcc/"
      "--sink_iceberg_checkpoint_dir"      = "s3://minerva-${local.env}-glue-checkpoints/checkpoints/unified/"
      "--sink_iceberg_assume_role_arn"     = "arn:aws:iam::851725323791:role/corp_dtd_dev_procintegratedingestionengineer"
      "--sink_iceberg_assume_session_name" = "mif-glue-iceberg"

      "--sink_trigger" = "availableNow"
    }
  }
  }

  # Dev endpoints set for local testing. Replace prod values with real endpoints
  # or point them to secrets manager in CI/CD.
  kafka_bootstrap_endpoint = {
    dev  = "localhost:9092"
    prod = "<prod-kafka-bootstrap-endpoint>"
  }

  # Dev schema registry for local testing.
  schema_registry_endpoint = {
    dev  = "http://localhost:8081"
    prod = "<prod-schema-registry-url>"
  }

  miw_account_id = {
    dev  = "<dev-aws-account-id>"
    prod = "<prod-aws-account-id>"
  }
}