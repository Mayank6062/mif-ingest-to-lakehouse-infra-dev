locals {
  glue_jobs = {
    "audit_test_glue_job" = {
      name                = "audit-test-glue-job"
      role_arn            = var.glue_execution_role_arn
      database_name       = aws_s3_bucket.data_lake.id
      job_type            = "pythonshell"
      glue_version        = "4.0"
      max_retries         = 1
      timeout             = 2880
      number_of_workers   = 2
      worker_type         = "G.1X"
      default_arguments = {
        "--job-bookmark-option" = "job-bookmark-enabled"
        "--enable-glue-datacatalog" = "true"
      }
    }
  }
}
