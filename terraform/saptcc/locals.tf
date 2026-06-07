locals {
  env      = "dev"
  ent_func = "CORP"
  subgroup = "CORP_DTD"

  # Glue jobs for SAPTCC
  glue_jobs = {
    test-override-job = {
      command = {
        name            = "glueetl"
        script_location = "s3://minerva-dev-src-corp/glue_scripts/kafka-to-iceberg-batch-saptcc-test-override.py"
      }
      connections = ["Kafka"]
      description = "Kafka to Iceberg batch job for SAPTCC test-override"
      
      default_arguments = {
        "--job-language"                        = "python"
        "--job-bookmark-option"                 = "job-bookmark-enable"
        "--source_kafka_bootstrap_endpoint"     = local.kafka_bootstrap_endpoint
        "--source_kafka_secret_name"            = "minerva-dev-corp-mif-saptcc-gluejob-sa-cc-api-creds"
        "--source_kafka_topic"                  = "dev.saptcc.test-override.raw"
        "--sink_iceberg_database"               = "lh_sap_tcc_raw_dev"
        "--sink_iceberg_table"                  = "test_override"
        "--sink_iceberg_warehouse"              = "s3://minerva-dev-src-corp/current/prd/raw/sap_tcc/"
        "--sink_assume_role_arn"                = "arn:aws:iam::851725323791:role/corp_dtd_dev_procintegratedingestionengineer"
        "--tls_enabled"                         = "true"
        "--schema_registry_endpoint"            = local.schema_registry_endpoint
        "--schema_registry_auth"                = local.schema_registry_auth
        "--iceberg_snapshot_isolation"          = "true"
        "--stop_before_start"                   = "true"
      }
      
      execution_class = "FLEX"
      glue_version    = "4.0"
      max_capacity    = 2.0
      number_of_workers = 2
      worker_type     = "G.1X"
      timeout         = 60
    }
  }
}
