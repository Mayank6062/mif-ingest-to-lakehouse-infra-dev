module "audit_test_sys_glue" {
  source = "./modules/glue"
  
  glue_jobs = local.glue_jobs
  
  environment = var.environment
}
