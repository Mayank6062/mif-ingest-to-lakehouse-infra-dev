module "glue_jobs" {
  for_each = local.glue_jobs

  source = "./../../../../modules/glue_job"

  glue_job_name        = each.key
  glue_job_description = each.value.description
  glue_job_command     = each.value.command
  glue_job_connections = each.value.connections
  glue_job_defaults    = each.value.default_arguments
  glue_version         = each.value.glue_version
  max_capacity         = each.value.max_capacity
  timeout              = each.value.timeout
  
  job_bookmark_option = each.value.default_arguments["--job-bookmark-option"]
  
  tags = merge(
    local.common_tags,
    {
      job_key       = each.key
      ent_func      = local.ent_func
      source_system = "saptcc"
    }
  )
}
