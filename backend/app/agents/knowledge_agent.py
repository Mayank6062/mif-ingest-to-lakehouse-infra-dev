"""
Knowledge Agent — derives values from topic and checks source system existence.
All derivation is deterministic: NO LLM call needed here.
Rules come from terraform_template.json field_derivation_logic.
"""

import logging

from app.knowledge.loader import get_knowledge_base
from app.services.github_service import GitHubService


logger = logging.getLogger(__name__)


class KnowledgeAgent:
    """
    Responsibilities:
    1. Derive environment, source_system, schema_grain, job_key, kafka_secret from topic
    2. Check if source system folder already exists
    3. Return source system pattern type
    """

    def __init__(self):
        self.kb = get_knowledge_base()

    # ── Topic derivation ──────────────────────────────────────────────────────

    def derive_from_topic(self, topic: str) -> dict:
        """
        Given a validated topic like: dev.saptcc.multi-1.raw
        Returns dict with all derived fields.
        """
        parts = topic.strip().split(".")
        # parts[0] = env, parts[1] = source_system, parts[2] = schema_grain, parts[3] = "raw"
        env = parts[0]
        source_system = parts[1]
        schema_grain = parts[2]

        # Job key derivation: kafka-to-iceberg-batch-{source_system}-{schema_grain}
        job_key = f"kafka-to-iceberg-batch-{source_system}-{schema_grain}"

        # Kafka secret name: minerva-${env}-corp-mif-{source_system}-gluejob-sa-cc-api-creds
        kafka_secret_name = f"minerva-{env}-corp-mif-{source_system}-gluejob-sa-cc-api-creds"

        return {
            "environment": env,
            "source_system": source_system,
            "schema_grain": schema_grain,
            "job_key": job_key,
            "kafka_secret_name": kafka_secret_name,
        }

    # ── Source system detection ───────────────────────────────────────────────

    def check_source_system(self, source_system: str) -> dict:
        """
        Returns:
          - exists: bool (authoritative GitHub repository decision)
          - pattern_type: "local_module" | "external_module" | "new"
          - display_name: human-readable description
        """
        kb_exists = self.kb.source_system_exists(source_system)
        info = self.kb.get_source_system_info(source_system)
        display = info.get("display_name", source_system.upper()) if info else source_system.upper()

        repo_state = GitHubService().get_source_system_repository_state(source_system)
        github_exists = repo_state["github_exists"]
        exists = github_exists
        pattern = self.kb.get_pattern_type(source_system) if exists and info else "new"

        logger.info(
            "Source-system decision: source_system=%s knowledge_base_exists=%s github_exists=%s final_exists=%s decision_source=github path=%s",
            source_system,
            kb_exists,
            github_exists,
            exists,
            repo_state["locals_path"],
        )

        return {
            "source_system_exists": exists,
            "source_system_pattern": pattern,
            "source_system_display_name": display,
            "knowledge_base_source_system_exists": kb_exists,
            "github_source_system_exists": github_exists,
            "source_system_decision_source": "github",
            "source_system_locals_path": repo_state["locals_path"],
        }

    # ── Files derivation ──────────────────────────────────────────────────────

    def get_files_to_modify(
        self,
        source_system: str,
        source_system_exists: bool,
        source_system_pattern: str,
    ) -> list[str]:
        """
        Returns the list of files that must be modified/created.

        KEY INSIGHT from real saptcc folder:
        - glue.tf uses `for_each = local.glue_jobs` — it picks up new jobs automatically.
        - For EXISTING source systems: ONLY locals.tf needs updating.
        - For NEW source systems: create both locals.tf AND glue.tf.
        """
        if source_system_exists:
            # ONLY locals.tf — glue.tf's for_each picks up new entries automatically
            return [
                f"{source_system}/locals.tf",
            ]
        else:
            # New source system — create both Terraform files
            return [
                f"{source_system}/locals.tf",
                f"{source_system}/glue.tf",
            ]

    def get_pr_checklist(
        self,
        source_system: str,
        source_system_exists: bool,
        job_key: str,
    ) -> list[str]:
        """PR checklist items the user should verify."""
        if source_system_exists:
            # Existing system: only locals.tf changes
            base = [
                f"✅ `{job_key}` block added to `{source_system}/locals.tf`",
                "✅ Job block is inside the `glue_jobs = { }` map",
                "✅ `--source_kafka_secret_name` uses `minerva-${local.env}-corp-mif-...` format",
                "✅ `--source_kafka_topic` uses `${local.env}.{source}.{grain}.raw` format",
                "✅ `--sink_iceberg_database` and warehouse paths are correct",
                "✅ `stop_before_start = true` is present",
                "✅ Worker type and count within allowed limits (G.025X/G.1X/G.2X/G.4X, 1-10)",
                "⚠️ `glue.tf` does NOT need changes — `for_each = local.glue_jobs` auto-picks up the new entry",
            ]
        else:
            base = [
                f"✅ New folder `{source_system}/` created",
                f"✅ `locals.tf` created with correct `ent_func`, `subgroup`, `glue_jobs` map",
                f"✅ `glue.tf` created with standard `module \"glue_jobs\" {{ for_each = local.glue_jobs }}` block",
                "✅ `kafka_bootstrap_endpoint`, `schema_registry_endpoint`, `miw_account_id` maps defined in locals.tf",
                "✅ First job entry added to `glue_jobs` map",
                "✅ Worker type and count within allowed limits",
            ]
        return base

    def get_new_source_checklist(self, source_system: str) -> list[str]:
        """UI-facing onboarding checklist for a brand-new source system."""
        return [
            f"Create `{source_system}/locals.tf` with file-level locals and a `glue_jobs` map",
            f"Create `{source_system}/glue.tf` with `for_each = local.glue_jobs`",
            "Add the first job entry to the new `glue_jobs` map",
        ]

    # ── Sink config derivation ────────────────────────────────────────────────

    def derive_sink_config(self, source_system: str, environment: str) -> dict:
        """
        Deterministically derive the 3 sink config values from source system info.

        Priority:
          1. source_systems.json entry has explicit `sink_config` block → use it (with ${env} expanded)
          2. Entry has `ent_func` + `domain` → use pattern derivation rules
          3. No info → fall back to generic AGTR-domain pattern

        Returns dict with keys: iceberg_database, iceberg_warehouse, assume_role_arn
        """
        info = self.kb.get_source_system_info(source_system)
        env = environment.lower()

        # ── 1. Explicit sink_config in source_systems.json ─────────────────
        if info and info.get("sink_config"):
            sc = info["sink_config"]
            return {
                "iceberg_database": sc.get("iceberg_database", "").replace("${env}", env),
                "iceberg_warehouse": sc.get("iceberg_warehouse", "").replace("${env}", env),
                "assume_role_arn": sc.get("assume_role_arn", "").replace("${env}", env),
            }

        # ── 2. Derive from ent_func + domain ──────────────────────────────
        ent_func = (info.get("ent_func", "AGTR") if info else "AGTR").lower()
        subgroup = (info.get("subgroup", "") if info else "")

        # Map ent_func → s3 bucket domain fragment
        ent_func_to_s3 = {
            "agtr": "agtr",
            "corp": "corp",
            "food": "food",
            "spec": "spec",
        }
        s3_domain = ent_func_to_s3.get(ent_func, ent_func)

        # Map subgroup → role name segment (if available)
        # e.g. CORP_DTD → corp_dtd ; AGTR_APAC → agtr_apac
        if subgroup:
            role_prefix = subgroup.lower().replace("-", "_")
        else:
            role_prefix = f"{ent_func}_apac"

        # Standard naming patterns
        iceberg_database = f"minerva_{env}_src_{ent_func}_{source_system}_prd_raw_db"
        iceberg_warehouse = f"s3://minerva-{env}-src-{s3_domain}/current/prd/raw/{source_system}/"

        # Attempt to read the AWS account ID from the source system entry.
        # A placeholder is used if no account ID is configured so that Terraform
        # plan will fail-fast with a clear, human-readable error rather than
        # silently committing a fake ARN.  The real account ID must be set in
        # source_systems.json under "aws_account_id" or provided via sink_config.
        aws_account_id = (info.get("aws_account_id", "") if info else "").strip()
        if not aws_account_id:
            aws_account_id = "<AWS_ACCOUNT_ID_REQUIRED>"

        assume_role_arn = (
            f"arn:aws:iam::{aws_account_id}:role/"
            f"{role_prefix}_{env}_procintegratedingestionengineer"
        )

        return {
            "iceberg_database": iceberg_database,
            "iceberg_warehouse": iceberg_warehouse,
            "assume_role_arn": assume_role_arn,
        }
