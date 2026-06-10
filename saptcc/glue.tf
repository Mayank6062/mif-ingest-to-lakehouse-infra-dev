module "glue_jobs" {
  for_each = local.glue_jobs

  source = "git::https://git.cglcloud.com/mayank/mif-ingest-to-lakehouse-infra-dev.git/mayank/glue_job?ref=main"
  env    = local.env
  name   = each.key

  existing_iam_role_arn = lookup(each.value, "existing_iam_role_arn", null)
  glue_version          = lookup(each.value, "glue_version", "")
  job_type              = lookup(each.value, "job_type", "kafka_to_iceberg")
  job_version           = lookup(each.value, "job_version", {})
  topic_name            = lookup(each.value, "topic_name", "")
  stop_before_start     = lookup(each.value, "stop_before_start", false)
  number_of_workers     = lookup(each.value, "number_of_workers", 2)
  worker_type           = lookup(each.value, "worker_type", "G.1X")

  extra_py_files   = lookup(each.value, "extra_py_files", {})
  trigger_schedule = lookup(each.value, "trigger_schedule", "")

  glue_job_arguments = lookup(each.value, "glue_job_arguments", {})

  secretsmanager_secret_name = lookup(lookup(each.value, "glue_job_arguments", null), "--cc_secret_name", null)
}