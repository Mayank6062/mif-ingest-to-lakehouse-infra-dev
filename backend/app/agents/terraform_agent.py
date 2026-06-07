"""
Terraform Agent — generates the exact HCL from the terraform_template.json template.
Template rendering uses str.replace() on {{placeholder}} patterns. All logic is deterministic.
"""

from app.knowledge.loader import get_knowledge_base


# ── HCL string safety ─────────────────────────────────────────────────────────

def escape_hcl_string(value: str) -> str:
    """
    Escape a string value for safe interpolation inside a quoted HCL string ("...").

    Applied to every user-controlled field before it is placed into an HCL template.
    The escape order is significant — backslashes MUST be escaped first to avoid
    double-escaping sequences introduced by later steps.

    Sequences escaped:
      \\   →  \\\\   backslash (must be first)
      "    →  \\"    HCL string delimiter
      \\n  →  \\\\n  newline — would terminate the HCL statement
      \\r  →  \\\\r  carriage return
      ${   →  $${    Terraform string interpolation sequence
      %{   →  %%{    Terraform template directive sequence
    """
    if not value:
        return value
    value = value.replace("\\", "\\\\")   # 1. backslash — MUST be first
    value = value.replace('"', '\\"')      # 2. double quote
    value = value.replace("\n", "\\n")     # 3. newline
    value = value.replace("\r", "\\r")     # 4. carriage return
    value = value.replace("${", "$${")     # 5. Terraform interpolation sequence
    value = value.replace("%{", "%%{")     # 6. Terraform directive sequence
    return value


# ── Fixed constants (from SOP and knowledge base) ───────────────────────────

ICEBERG_CATALOG_TYPE = "glue"
ASSUME_SESSION_NAME = "mif-glue-iceberg"
SINK_TRIGGER = "availableNow"
SCHEMA_REGISTRY_PREFIX = "schema-registry"


class TerraformAgent:
    """
    Generates the Terraform HCL block for a new Glue job.
    Fills the template from terraform_template.json.
    """

    def __init__(self):
        self.kb = get_knowledge_base()

    def generate(self, state: dict) -> str:
        """
        Generate the complete Terraform HCL block from the current state.
        Returns the rendered HCL string.
        """
        template_str = self.kb.terraform_hcl_template
        if not template_str:
            return self._fallback_generate(state)

        # Build the context dict for template rendering
        ctx = self._build_context(state)

        # Use Jinja2 to render — the template uses {{variable}} syntax
        # Convert {{}} to Jinja2 format
        jinja_template = template_str.replace("{{", "{{").replace("}}", "}}")
        # Actually the template uses {{placeholder}} — let's replace with Jinja2 vars
        rendered = self._render_template(template_str, ctx)
        return rendered

    def _build_context(self, state: dict) -> dict:
        """Build the complete context dict for template rendering."""
        env = state.get("environment", "dev")
        source_system = state.get("source_system", "")
        schema_grain = state.get("schema_grain", "")
        job_key = state.get("job_key", f"kafka-to-iceberg-batch-{source_system}-{schema_grain}")
        worker_type = state.get("worker_type", "G.1X")
        number_of_workers = state.get("number_of_workers", 2)
        job_type = state.get("job_type", "unified")
        job_version = state.get("job_version", "0.3.0")
        glue_version = state.get("glue_version", "5.1")
        iceberg_database = state.get("iceberg_database", "")
        iceberg_warehouse = state.get("iceberg_warehouse", "")
        # checkpoint_dir is a FIXED Terraform interpolation — NOT user-provided; never escaped
        checkpoint_dir_hcl = 's3://minerva-${local.env}-glue-checkpoints/checkpoints/unified/'
        assume_role_arn = state.get("assume_role_arn", "")
        scheduling_mode = state.get("scheduling_mode", "manual")
        trigger_schedule = state.get("trigger_schedule") or ""

        # ── HCL string safety: escape all user-controlled string values before
        #    they are interpolated into quoted HCL string contexts.
        #    checkpoint_dir_hcl is a fixed constant — NOT escaped.
        #    number_of_workers is coerced to int elsewhere — NOT escaped.
        #    scheduling_mode is allowlist-validated — NOT escaped (not in HCL string).
        return {
            "job_key":           escape_hcl_string(job_key),
            # In generated HCL, use ${local.env} Terraform interpolation — not the literal env value
            "source_system":     escape_hcl_string(source_system),
            "schema_grain":      escape_hcl_string(schema_grain),
            "worker_type":       escape_hcl_string(worker_type),
            "number_of_workers": number_of_workers,
            "job_type":          escape_hcl_string(job_type),
            "job_version":       escape_hcl_string(job_version),
            "glue_version":      escape_hcl_string(glue_version),
            "iceberg_database":  escape_hcl_string(iceberg_database),
            "iceberg_warehouse": escape_hcl_string(iceberg_warehouse),
            "checkpoint_dir_hcl": checkpoint_dir_hcl,
            "assume_role_arn":   escape_hcl_string(assume_role_arn),
            "scheduling_mode":   scheduling_mode,
            "trigger_schedule":  escape_hcl_string(trigger_schedule),
        }

    def _render_template(self, template_str: str, ctx: dict) -> str:
        """
        Replace {{placeholder}} with actual values.
        Handles the template format used in terraform_template.json.
        NOTE: ${local.env} strings in the template are Terraform interpolations —
        they pass through unchanged and are NOT Python template variables.
        """
        result = template_str
        for key, value in ctx.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))

        # Handle optional trigger_schedule line
        # Template has: glue_version line \n {{trigger_schedule_line}} \n number_of_workers
        # So replacement must NOT include leading/trailing \n (template provides them)
        # For scheduled: insert the line with 4-space indent + trailing \n (blank line before workers)
        # For manual: replace with empty string (template \n + empty + \n = single blank line)
        scheduling_mode = ctx.get("scheduling_mode", "manual")
        trigger_schedule = ctx.get("trigger_schedule", "")
        if scheduling_mode == "scheduled" and trigger_schedule:
            result = result.replace(
                "{{trigger_schedule_line}}",
                f'    trigger_schedule  = "{trigger_schedule}"'
            )
        else:
            result = result.replace("{{trigger_schedule_line}}", "")

        return result

    def _fallback_generate(self, state: dict) -> str:
        """
        Fallback HCL generator when no template in knowledge base.
        Matches the EXACT structure from saptcc/locals.tf.
        ent_func/subgroup are FILE-LEVEL — not emitted in this job block.
        """
        ctx = self._build_context(state)
        source_system = ctx["source_system"]
        schema_grain = ctx["schema_grain"]
        job_key = ctx["job_key"]
        worker_type = ctx["worker_type"]
        num_workers = ctx["number_of_workers"]
        job_type = ctx["job_type"]
        job_version = ctx["job_version"]
        glue_version = ctx["glue_version"]
        iceberg_db = ctx["iceberg_database"]
        warehouse = ctx["iceberg_warehouse"]
        assume_arn = ctx["assume_role_arn"]
        scheduling_mode = ctx["scheduling_mode"]
        trigger_schedule = ctx["trigger_schedule"]

        # Optional trigger_schedule line — only present when scheduled
        # Position: after glue_version, before number_of_workers (exact saptcc structure)
        trigger_line = ""
        if scheduling_mode == "scheduled" and trigger_schedule:
            # 4-space indent to match locals.tf; trailing \n creates blank line before number_of_workers
            trigger_line = f'    trigger_schedule  = "{trigger_schedule}"\n'

        # NOTE: ${local.env} below is a Terraform interpolation — written literally
        hcl = f'''  "{job_key}" = {{
    job_type     = "{job_type}"
    job_version  = "{job_version}"
    glue_version = "{glue_version}"
{trigger_line}
    number_of_workers = {num_workers}
    worker_type       = "{worker_type}"
    stop_before_start = true

    glue_job_arguments = {{
      "--source"                   = "kafka"
      "--source_kafka_endpoint"    = local.kafka_bootstrap_endpoint[local.env]
      "--source_kafka_secret_name" = "minerva-${{local.env}}-corp-mif-{source_system}-gluejob-sa-cc-api-creds"
      "--source_kafka_topic"       = "${{local.env}}.{source_system}.{schema_grain}.raw"

      "--transformer1"              = "timestamp"
      "--transformer1_column"       = "processing_timestamp"
      "--transformer1_value_format" = "json"

      "--transformer2"                 = "kafka_unpack"
      "--transformer2_metadata_column" = "__metadata__"

      "--sink_transformer1"                          = "kafka_split"
      "--sink_transformer1_schema_registry_endpoint" = local.schema_registry_endpoint[local.env]
      "--sink_transformer1_secret_name"              = "minerva-${{local.env}}-corp-mif-{source_system}-gluejob-sa-cc-api-creds"

      "--sink"                             = "iceberg"
      "--sink_iceberg_catalog_type"        = "glue"
      "--sink_iceberg_catalog_id"          = local.miw_account_id[local.env]
      "--sink_iceberg_database"            = "{iceberg_db}"
      "--sink_iceberg_warehouse"           = "{warehouse}"
      "--sink_iceberg_checkpoint_dir"      = "s3://minerva-${{local.env}}-glue-checkpoints/checkpoints/unified/"
      "--sink_iceberg_assume_role_arn"     = "{assume_arn}"
      "--sink_iceberg_assume_session_name" = "mif-glue-iceberg"

      "--sink_trigger" = "availableNow"
    }}
  }}'''

        return hcl

    def get_locals_tf_entry(self, state: dict) -> str:
        """
        Generate the entry that goes into locals.tf (inside the glue_jobs map).
        For EXISTING source systems this is the ONLY file that changes.
        """
        hcl = self.generate(state)
        return f"# Add inside the glue_jobs = {{ ... }} map in locals.tf:\n{hcl}"

    def generate_full_locals_tf(self, state: dict) -> str:
        """
        For NEW source systems: generate the COMPLETE locals.tf file content.
        Includes: ent_func, subgroup, glue_jobs map with the job entry,
        kafka_bootstrap_endpoint, schema_registry_endpoint, miw_account_id.
        Matches the repo pattern exactly (see process doc Section 11).
        """
        ent_func = escape_hcl_string(state.get("ent_func", "AGTR"))
        subgroup = escape_hcl_string(state.get("subgroup", "APAC"))
        source_system = state.get("source_system", "")
        job_entry = self.generate(state)

        return f'''locals {{
  ent_func = "{ent_func}"
  subgroup = "{subgroup}"

  glue_jobs = {{
{job_entry}
  }}

  kafka_bootstrap_endpoint = {{
    dev  = "<dev-kafka-bootstrap-endpoint>"
    prod = "<prod-kafka-bootstrap-endpoint>"
  }}

  schema_registry_endpoint = {{
    dev  = "<dev-schema-registry-url>"
    prod = "<prod-schema-registry-url>"
  }}

  miw_account_id = {{
    dev  = "<dev-aws-account-id>"
    prod = "<prod-aws-account-id>"
  }}
}}'''

    def get_new_source_system_locals_header(self, state: dict) -> str:
        """
        For NEW source systems: generate the file-level locals header.
        ent_func and subgroup are FILE-LEVEL, not per-job.
        """
        ent_func = escape_hcl_string(state.get("ent_func", "AGTR"))
        subgroup = escape_hcl_string(state.get("subgroup", "APAC"))
        return f'''locals {{
  ent_func = "{ent_func}"
  subgroup = "{subgroup}"

  glue_jobs = {{
    # Add job entry here
  }}

  kafka_bootstrap_endpoint = {{
    dev  = "<dev-kafka-bootstrap-endpoint>"
    prod = "<prod-kafka-bootstrap-endpoint>"
  }}

  schema_registry_endpoint = {{
    dev  = "<dev-schema-registry-url>"
    prod = "<prod-schema-registry-url>"
  }}

  miw_account_id = {{
    dev  = "<dev-aws-account-id>"
    prod = "<prod-aws-account-id>"
  }}
}}'''

    def get_glue_tf_content(self, source_system: str) -> str:
        """
        Returns the standard glue.tf content for a source system folder.
        This is a single module block with for_each — NOT individual resources.
        This file is the SAME for all source systems and never changes when adding jobs.
        For EXISTING source systems, glue.tf is NEVER modified.
        """
        return f'''module "glue_jobs" {{
  for_each = local.glue_jobs

  source = "git::https://git.cglcloud.com/mayank/mif-ingest-to-lakehouse-infra-dev.git/mayank/glue_job?ref=main"
  env    = local.env
  name   = each.key

  existing_iam_role_arn = lookup(each.value, "existing_iam_role_arn", null)
  glue_version          = lookup(each.value, "glue_version", "")
  job_type              = lookup(each.value, "job_type", "kafka_to_iceberg")
  job_version           = lookup(each.value, "job_version", {{}})
  topic_name            = lookup(each.value, "topic_name", "")
  stop_before_start     = lookup(each.value, "stop_before_start", false)
  number_of_workers     = lookup(each.value, "number_of_workers", 2)
  worker_type           = lookup(each.value, "worker_type", "G.1X")

  extra_py_files   = lookup(each.value, "extra_py_files", {{}})
  trigger_schedule = lookup(each.value, "trigger_schedule", "")

  glue_job_arguments = lookup(each.value, "glue_job_arguments", {{}})

  secretsmanager_secret_name = lookup(lookup(each.value, "glue_job_arguments", null), "--cc_secret_name", null)
}}'''

    def get_summary_table(self, state: dict) -> list[dict]:
        """Build the summary table rows for the Summary UI widget."""
        ctx = self._build_context(state)
        source_exists = state.get("source_system_exists", False)
        source_system = state.get("source_system", "")
        schema_grain = state.get("schema_grain", "")
        topic = state.get("topic", "")
        kafka_secret = state.get("kafka_secret_name", "")
        ent_func = state.get("ent_func", "")
        subgroup = state.get("subgroup", "")

        rows = [
            {"field": "Kafka Topic", "value": topic},
            {"field": "Environment", "value": state.get("environment", "").upper()},
            {"field": "Source System", "value": source_system},
            {"field": "Schema Grain", "value": schema_grain},
            {"field": "Job Key", "value": ctx["job_key"]},
            {"field": "Kafka Secret (HCL)", "value": f"minerva-${{local.env}}-corp-mif-{source_system}-gluejob-sa-cc-api-creds"},
            {"field": "Worker Type", "value": ctx["worker_type"]},
            {"field": "Worker Count", "value": str(ctx["number_of_workers"])},
            {"field": "Job Type", "value": ctx["job_type"]},
            {"field": "Job Version", "value": ctx["job_version"]},
            {"field": "Glue Version", "value": ctx["glue_version"]},
            {"field": "Iceberg Database", "value": ctx["iceberg_database"]},
            {"field": "Warehouse", "value": ctx["iceberg_warehouse"]},
            {"field": "Checkpoint Dir", "value": "s3://minerva-${local.env}-glue-checkpoints/checkpoints/unified/ (fixed)"},
            {"field": "Assume Role ARN", "value": ctx["assume_role_arn"]},
            {"field": "Scheduling Mode", "value": ctx["scheduling_mode"]},
            {"field": "Source System Status",
             "value": "✅ Existing folder (only locals.tf changes)" if source_exists else "⚠️ NEW — locals.tf + glue.tf will be created"},
        ]
        if not source_exists and ent_func:
            rows.insert(7, {"field": "Enterprise Func (file-level)", "value": ent_func})
            rows.insert(8, {"field": "Subgroup (file-level)", "value": subgroup})
        return rows
