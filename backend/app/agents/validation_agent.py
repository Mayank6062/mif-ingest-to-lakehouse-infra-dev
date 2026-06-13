"""
Validation Agent — runs ALL business validation rules from validation_rules.json.
All logic is deterministic: NO LLM involved.
Returns list of ValidationResult objects with pass/warn/fail per rule.
"""

import re
from app.knowledge.loader import get_knowledge_base
from app.models.chat import ValidationResult

# Expose GitHubService symbol for tests that patch it via app.agents.validation_agent.GitHubService
from app.services.github_service import GitHubService  # re-export for tests


class ValidationAgent:
    """
    Validates every field against the corresponding rule in validation_rules.json.
    """

    def __init__(self):
        self.kb = get_knowledge_base()

    # ── Master validation entry point ─────────────────────────────────────────

    def validate_all(self, state: dict) -> list[dict]:
        """
        Run all applicable validations for the current state.
        Returns list of ValidationResult dicts.
        """
        results = []
        results.extend(self._validate_topic(state.get("topic", "")))
        results.extend(self._validate_worker_config(state))
        results.extend(self._validate_sink_config(state))
        results.extend(self._validate_enterprise(state))
        results.extend(self._validate_subgroup(state))
        results.extend(self._validate_job_type(state))
        results.extend(self._validate_duplicate_job(state))
        results.extend(self._validate_hcl_safe_fields(state))
        results.extend(self._validate_versions(state))
        return results

    def has_failures(self, results: list[dict]) -> bool:
        return any(r["result"] == "fail" for r in results)

    # ── Topic validation ──────────────────────────────────────────────────────

    def validate_topic(self, topic: str) -> tuple[bool, str]:
        """Quick check: returns (is_valid, error_message)."""
        topic = topic.strip()
        pattern = self.kb.topic_regex
        if not re.match(pattern, topic):
            return False, (
                f"Topic must match: `{pattern}`\n"
                f"Example: `dev.saptcc.multi-1.raw`\n"
                f"Format: `{{env}}.{{source_system}}.{{schema_grain}}.raw`\n"
                f"Allowed envs: dev, snd, prod"
            )
        return True, ""

    def _validate_topic(self, topic: str) -> list[dict]:
        results = []
        if not topic:
            results.append(ValidationResult(
                rule_id="TR-001",
                rule_name="Topic Format",
                result="fail",
                message="Kafka topic is required",
                field="topic",
            ).model_dump())
            return results

        topic = topic.strip()
        pattern = self.kb.topic_regex
        if not re.match(pattern, topic):
            results.append(ValidationResult(
                rule_id="TR-001",
                rule_name="Topic Format",
                result="fail",
                message=f"Topic '{topic}' does not match required pattern: {pattern}",
                field="topic",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="TR-001",
                rule_name="Topic Format",
                result="pass",
                message=f"Topic format is valid",
                field="topic",
            ).model_dump())

        # TR-003: segment count must be exactly 4
        segments = topic.split(".")
        if len(segments) != 4:
            results.append(ValidationResult(
                rule_id="TR-003",
                rule_name="Topic Segment Count",
                result="fail",
                message=(
                    f"Topic '{topic}' has {len(segments)} segment(s) — must have exactly 4. "
                    "Required format: {env}.{source_system}.{schema_grain}.raw"
                ),
                field="topic",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="TR-003",
                rule_name="Topic Segment Count",
                result="pass",
                message="Topic has exactly 4 segments ✓",
                field="topic",
            ).model_dump())

            # TR-005: source system segment (segment[1]) must be lowercase alphanumeric + hyphens
            source_seg = segments[1]
            source_seg_pattern = re.compile(r"^[a-z][a-z0-9-]*$")
            if not source_seg_pattern.match(source_seg):
                results.append(ValidationResult(
                    rule_id="TR-005",
                    rule_name="Source System Segment Format",
                    result="fail",
                    message=(
                        f"Source system segment '{source_seg}' is invalid. "
                        "Must start with a lowercase letter and contain only lowercase letters, "
                        "digits, and hyphens (no uppercase, spaces, or special characters)."
                    ),
                    field="topic",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="TR-005",
                    rule_name="Source System Segment Format",
                    result="pass",
                    message=f"Source system segment '{source_seg}' is valid ✓",
                    field="topic",
                ).model_dump())

        # TR-004: env must be dev/snd/prod
        env = topic.split(".")[0] if topic else ""
        allowed_envs = self.kb.allowed_environments
        if env not in allowed_envs:
            results.append(ValidationResult(
                rule_id="TR-004",
                rule_name="Environment Value",
                result="fail",
                message=f"Environment '{env}' is not allowed. Must be one of: {allowed_envs}",
                field="topic",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="TR-004",
                rule_name="Environment Value",
                result="pass",
                message=f"Environment '{env}' is valid",
                field="topic",
            ).model_dump())

        # TR-002: must end with .raw
        if topic and not topic.endswith(".raw"):
            results.append(ValidationResult(
                rule_id="TR-002",
                rule_name="Topic Suffix",
                result="fail",
                message="Topic must end with '.raw'. Example: dev.saptcc.multi-1.raw",
                field="topic",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="TR-002",
                rule_name="Topic Suffix",
                result="pass",
                message="Topic ends with '.raw' ✓",
                field="topic",
            ).model_dump())

        return results

    # ── Worker config validation ──────────────────────────────────────────────

    def _validate_worker_config(self, state: dict) -> list[dict]:
        results = []
        worker_type = state.get("worker_type", "G.1X")
        number_of_workers = int(state.get("number_of_workers", 2))
        allowed = self.kb.allowed_worker_types

        # WR-001: worker_type must be in allowed list
        if worker_type not in allowed:
            results.append(ValidationResult(
                rule_id="WR-001",
                rule_name="Worker Type",
                result="fail",
                message=f"Worker type '{worker_type}' not allowed. Must be: {allowed}",
                field="worker_type",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="WR-001",
                rule_name="Worker Type",
                result="pass",
                message=f"Worker type '{worker_type}' is valid",
                field="worker_type",
            ).model_dump())

        # WR-002: number_of_workers must be 1-10
        if not (1 <= number_of_workers <= 10):
            results.append(ValidationResult(
                rule_id="WR-002",
                rule_name="Worker Count",
                result="fail",
                message=f"Worker count {number_of_workers} out of range. Must be 1-10.",
                field="number_of_workers",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="WR-002",
                rule_name="Worker Count",
                result="pass",
                message=f"Worker count {number_of_workers} is valid",
                field="number_of_workers",
            ).model_dump())

        # WR-003: G.025X can only have 1 worker
        if worker_type == "G.025X" and number_of_workers > 1:
            results.append(ValidationResult(
                rule_id="WR-003",
                rule_name="G.025X Worker Limit",
                result="fail",
                message="G.025X worker type supports maximum 1 worker",
                field="number_of_workers",
            ).model_dump())

        return results

    # ── Sink config validation ─────────────────────────────────────────────────

    def _validate_sink_config(self, state: dict) -> list[dict]:
        results = []
        db = state.get("iceberg_database", "") or ""
        warehouse = state.get("iceberg_warehouse", "") or ""
        assume_role = state.get("assume_role_arn", "") or ""
        # checkpoint_dir is auto-derived as fixed Terraform interpolation — not validated here

        # DBR-001: database required
        if not db:
            results.append(ValidationResult(
                rule_id="DBR-001",
                rule_name="Iceberg Database",
                result="fail",
                message="iceberg_database is required",
                field="iceberg_database",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="DBR-001",
                rule_name="Iceberg Database",
                result="pass",
                message=f"iceberg_database: {db}",
                field="iceberg_database",
            ).model_dump())

        # SWR-001: warehouse must start with s3://
        if not warehouse:
            results.append(ValidationResult(
                rule_id="SWR-001",
                rule_name="S3 Warehouse Path",
                result="fail",
                message="iceberg_warehouse is required",
                field="iceberg_warehouse",
            ).model_dump())
        elif not warehouse.startswith("s3://"):
            results.append(ValidationResult(
                rule_id="SWR-001",
                rule_name="S3 Warehouse Path",
                result="fail",
                message="iceberg_warehouse must start with 's3://'",
                field="iceberg_warehouse",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="SWR-001",
                rule_name="S3 Warehouse Path",
                result="pass",
                message="Warehouse path starts with s3:// ✓",
                field="iceberg_warehouse",
            ).model_dump())

        # SWR-002: warehouse must end with /  (auto-correctable)
        if warehouse and not warehouse.endswith("/"):
            results.append(ValidationResult(
                rule_id="SWR-002",
                rule_name="S3 Warehouse Trailing Slash",
                result="warn",
                message=(
                    f"iceberg_warehouse should end with '/'. "
                    f"Suggested correction: '{warehouse}/'"
                ),
                field="iceberg_warehouse",
            ).model_dump())
        elif warehouse and warehouse.endswith("/"):
            results.append(ValidationResult(
                rule_id="SWR-002",
                rule_name="S3 Warehouse Trailing Slash",
                result="pass",
                message="Warehouse path ends with '/' ✓",
                field="iceberg_warehouse",
            ).model_dump())

        # DBR-002: database must contain the environment name (WARN)
        env = state.get("environment", "")
        if db and env and env.lower() not in db.lower():
            results.append(ValidationResult(
                rule_id="DBR-002",
                rule_name="Database Contains Environment",
                result="warn",
                message=(
                    f"iceberg_database '{db}' does not contain the environment name '{env}'. "
                    f"Expected format: minerva_{env}_src_..._raw_db"
                ),
                field="iceberg_database",
            ).model_dump())
        elif db and env:
            results.append(ValidationResult(
                rule_id="DBR-002",
                rule_name="Database Contains Environment",
                result="pass",
                message=f"Database name contains environment '{env}' ✓",
                field="iceberg_database",
            ).model_dump())

        # DBR-003: database must contain 'raw' (ERROR — MIF convention)
        if db and "raw" not in db.lower():
            results.append(ValidationResult(
                rule_id="DBR-003",
                rule_name="Database Contains 'raw'",
                result="fail",
                message=(
                    f"iceberg_database '{db}' must contain 'raw'. "
                    f"Example: minerva_{env}_src_corp_{state.get('source_system','')}_prd_raw_db"
                ),
                field="iceberg_database",
            ).model_dump())
        elif db:
            results.append(ValidationResult(
                rule_id="DBR-003",
                rule_name="Database Contains 'raw'",
                result="pass",
                message="Database name contains 'raw' ✓",
                field="iceberg_database",
            ).model_dump())

        # SER-001: assume_role_arn must be valid ARN format
        if not assume_role:
            results.append(ValidationResult(
                rule_id="SER-001",
                rule_name="IAM Role ARN",
                result="fail",
                message="assume_role_arn is required",
                field="assume_role_arn",
            ).model_dump())
        elif not assume_role.startswith("arn:aws:iam::"):
            results.append(ValidationResult(
                rule_id="SER-001",
                rule_name="IAM Role ARN",
                result="fail",
                message="assume_role_arn must start with 'arn:aws:iam::'. Example: arn:aws:iam::123456789012:role/my-role",
                field="assume_role_arn",
            ).model_dump())
        elif "<AWS_ACCOUNT_ID_REQUIRED>" in assume_role:
            results.append(ValidationResult(
                rule_id="SER-001",
                rule_name="IAM Role ARN",
                result="fail",
                message=(
                    "assume_role_arn contains placeholder '<AWS_ACCOUNT_ID_REQUIRED>'. "
                    "Add 'aws_account_id' to the source system entry in source_systems.json "
                    "or provide an explicit sink_config.assume_role_arn."
                ),
                field="assume_role_arn",
            ).model_dump())
        else:
            # SER-002: account ID portion should be a 12-digit number
            arn_parts = assume_role.split(":")
            account_id = arn_parts[4] if len(arn_parts) > 4 else ""
            if not re.match(r"^\d{12}$", account_id):
                results.append(ValidationResult(
                    rule_id="SER-002",
                    rule_name="IAM ARN Account ID",
                    result="warn",
                    message=(
                        f"assume_role_arn account ID '{account_id}' is not a 12-digit number. "
                        "Verify the ARN is correct before creating the PR."
                    ),
                    field="assume_role_arn",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="SER-001",
                    rule_name="IAM Role ARN",
                    result="pass",
                    message="IAM role ARN format is valid ✓",
                    field="assume_role_arn",
                ).model_dump())

        return results

    # ── Subgroup validation ───────────────────────────────────────────────────

    def _validate_subgroup(self, state: dict) -> list[dict]:
        results = []
        subgroup = (state.get("subgroup") or "").strip().lower()
        allowed = self.kb.allowed_subgroups

        # SGR-001: subgroup must be one of allowed values — unknown/empty -> fail
        # SGR-001: enforce FAIL for empty/unknown/injection subgroup values
        # Per test requirements, these cases must be treated as failures.
        result_on_problem = "fail"

        if not subgroup:
            results.append(ValidationResult(
                rule_id="SGR-001",
                rule_name="Subgroup",
                result=result_on_problem,
                message=(
                    f"subgroup is {'required' if result_on_problem=='fail' else 'empty'}. "
                    f"Allowed values: {allowed}. Example: apac"
                ),
                field="subgroup",
            ).model_dump())
        elif subgroup not in allowed:
            results.append(ValidationResult(
                rule_id="SGR-001",
                rule_name="Subgroup",
                result=result_on_problem,
                message=(
                    f"subgroup '{subgroup}' is not in the allowed list {allowed}. "
                    f"{'Must be one of' if result_on_problem=='fail' else 'Suggested values:'} apac, na, latam"
                ),
                field="subgroup",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="SGR-001",
                rule_name="Subgroup",
                result="pass",
                message=f"subgroup '{subgroup}' is valid ✓",
                field="subgroup",
            ).model_dump())

        return results

    # ── Enterprise func validation ─────────────────────────────────────────────

    def _validate_enterprise(self, state: dict) -> list[dict]:
        results = []
        ent_func = state.get("ent_func", "AGTR")
        allowed = self.kb.allowed_enterprise_funcs

        if ent_func not in allowed:
            results.append(ValidationResult(
                rule_id="ER-001",
                rule_name="Enterprise Function",
                result="fail",
                message=f"ent_func '{ent_func}' not allowed. Must be: {allowed}",
                field="ent_func",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="ER-001",
                rule_name="Enterprise Function",
                result="pass",
                message=f"ent_func '{ent_func}' is valid",
                field="ent_func",
            ).model_dump())

        return results

    # ── Duplicate job detection (JR-002) ─────────────────────────────────────

    def _validate_duplicate_job(self, state: dict) -> list[dict]:
        """
        JR-002: detect whether job_key already exists inside locals.tf.
        Only runs when source_system_exists is True and terraform_hcl is not yet set
        (i.e. before generation).  Uses the GitHub service's file-read helper.
        Skips silently if GitHub credentials are unavailable.
        """
        results = []
        job_key      = state.get("job_key", "")
        source_sys   = state.get("source_system", "")
        src_exists   = state.get("source_system_exists", False)

        if not job_key or not source_sys or not src_exists:
            # Nothing to check: new system will create the file fresh
            return results

        try:
            # Use module-level GitHubService symbol so tests can patch
            # app.agents.validation_agent.GitHubService
            svc = GitHubService()
            repo = svc._get_repo()
            path = f"{source_sys}/locals.tf"
            file_obj = svc._get_file_content(repo, path, svc._base_branch)

            if file_obj is None:
                # File doesn't exist yet — no duplicate possible
                return results

            content = file_obj.decoded_content.decode("utf-8")
            # Check for the job key as a quoted HCL map key
            pattern = re.compile(
                r'["\']?' + re.escape(job_key) + r'["\']?\s*=\s*\{',
                re.MULTILINE,
            )
            if pattern.search(content):
                results.append(ValidationResult(
                    rule_id="JR-002",
                    rule_name="Duplicate Job Key",
                    result="fail",
                    message=(
                        f"Job key '{job_key}' already exists in "
                        f"'{path}' on branch '{svc._base_branch}'. "
                        "Rename the job or update the existing entry instead."
                    ),
                    field="job_key",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="JR-002",
                    rule_name="Duplicate Job Key",
                    result="pass",
                    message=f"Job key '{job_key}' is unique in {path} ✓",
                    field="job_key",
                ).model_dump())

        except Exception:
            # GitHub unavailable (e.g. no token in dev) — skip, do not block workflow
            pass

        return results

    # ── Job type validation ───────────────────────────────────────────────────

    def _validate_job_type(self, state: dict) -> list[dict]:
        results = []
        job_type = state.get("job_type", "unified")
        allowed = self.kb.allowed_job_types

        if job_type not in allowed:
            results.append(ValidationResult(
                rule_id="JOBT-001",
                rule_name="Job Type",
                result="fail",
                message=f"job_type '{job_type}' not allowed. Must be: {allowed}",
                field="job_type",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="JOBT-001",
                rule_name="Job Type",
                result="pass",
                message=f"job_type '{job_type}' is valid ✓",
                field="job_type",
            ).model_dump())

        # JOBT-002: scheduling_mode must be manual or scheduled
        scheduling_mode   = state.get("scheduling_mode", "manual")
        allowed_modes     = self.kb.allowed_scheduling_modes
        if scheduling_mode not in allowed_modes:
            results.append(ValidationResult(
                rule_id="JOBT-002",
                rule_name="Scheduling Mode",
                result="fail",
                message=(
                    f"scheduling_mode '{scheduling_mode}' is not allowed. "
                    f"Must be one of: {allowed_modes}"
                ),
                field="scheduling_mode",
            ).model_dump())
        else:
            results.append(ValidationResult(
                rule_id="JOBT-002",
                rule_name="Scheduling Mode",
                result="pass",
                message=f"scheduling_mode '{scheduling_mode}' is valid ✓",
                field="scheduling_mode",
            ).model_dump())

        # CRON-001: cron expression required when scheduling_mode = "scheduled"
        # (scheduling_mode is re-read below — intentional; already assigned above)
        trigger_schedule  = (state.get("trigger_schedule") or "").strip()
        cron_pattern = re.compile(
            r"^cron\(\s*\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s*\)$"
        )
        if scheduling_mode == "scheduled":
            if not trigger_schedule:
                results.append(ValidationResult(
                    rule_id="CRON-001",
                    rule_name="Cron Expression",
                    result="fail",
                    message=(
                        "trigger_schedule is required when scheduling_mode is 'scheduled'. "
                        "Example: cron(0 1 * * ? *)"
                    ),
                    field="trigger_schedule",
                ).model_dump())
            elif not cron_pattern.match(trigger_schedule):
                results.append(ValidationResult(
                    rule_id="CRON-001",
                    rule_name="Cron Expression",
                    result="fail",
                    message=(
                        f"trigger_schedule '{trigger_schedule}' is not a valid AWS cron expression. "
                        "Required format: cron(minutes hours day-of-month month day-of-week year). "
                        "Example: cron(0 1 * * ? *)"
                    ),
                    field="trigger_schedule",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="CRON-001",
                    rule_name="Cron Expression",
                    result="pass",
                    message=f"Cron expression '{trigger_schedule}' is valid ✓",
                    field="trigger_schedule",
                ).model_dump())

        return results
    # \u2500\u2500 HCL injection safety validation \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    def _validate_hcl_safe_fields(self, state: dict) -> list[dict]:
        """
        Structural character-safety checks for all fields that are interpolated
        directly into Terraform HCL string values.

        These checks run IN ADDITION to semantic validation (DBR-*, SWR-*, SER-*).
        They prevent HCL injection by enforcing strict character allowlists before
        any value reaches the terraform_agent template renderer.

        Rule IDs: DBR-CHAR-001, SWR-CHAR-001, SER-FULL-001, SCHED-001
        """
        results = []

        # DBR-CHAR-001: iceberg_database — alphanumeric, hyphens, underscores only
        db = (state.get("iceberg_database") or "").strip()
        _DB_SAFE = re.compile(r"^[a-zA-Z0-9_-]+$")
        if db:
            if not _DB_SAFE.match(db):
                results.append(ValidationResult(
                    rule_id="DBR-CHAR-001",
                    rule_name="Iceberg Database Character Safety",
                    result="fail",
                    message=(
                        f"iceberg_database '{db}' contains characters that are unsafe in HCL. "
                        "Only letters, digits, hyphens, and underscores are permitted. "
                        "Example: minerva_dev_src_agtr_saptcc_prd_raw_db"
                    ),
                    field="iceberg_database",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="DBR-CHAR-001",
                    rule_name="Iceberg Database Character Safety",
                    result="pass",
                    message="iceberg_database contains only HCL-safe characters \u2713",
                    field="iceberg_database",
                ).model_dump())

        # SWR-CHAR-001: iceberg_warehouse — full S3 URL pattern (safe chars only)
        warehouse = (state.get("iceberg_warehouse") or "").strip()
        _WH_SAFE = re.compile(r"^s3://[a-zA-Z0-9._/-]+/$")
        if warehouse:
            if not _WH_SAFE.match(warehouse):
                results.append(ValidationResult(
                    rule_id="SWR-CHAR-001",
                    rule_name="Iceberg Warehouse URL Safety",
                    result="fail",
                    message=(
                        f"iceberg_warehouse '{warehouse}' does not match the required safe URL pattern. "
                        "Must be: s3://<bucket>/<path>/ using only letters, digits, dots, hyphens, "
                        "underscores, and slashes, ending with /. "
                        "Example: s3://minerva-dev-src-agtr/current/prd/raw/sap_tce/"
                    ),
                    field="iceberg_warehouse",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="SWR-CHAR-001",
                    rule_name="Iceberg Warehouse URL Safety",
                    result="pass",
                    message="iceberg_warehouse URL is structurally safe for HCL \u2713",
                    field="iceberg_warehouse",
                ).model_dump())

        # SER-FULL-001: assume_role_arn — full AWS IAM role ARN pattern
        arn = (state.get("assume_role_arn") or "").strip()
        _ARN_SAFE = re.compile(
            r"^arn:aws:iam::\d{12}:role/[a-zA-Z0-9+=,.@_/-]+$"
        )
        if arn:
            if not _ARN_SAFE.match(arn):
                results.append(ValidationResult(
                    rule_id="SER-FULL-001",
                    rule_name="IAM Role ARN Full Validation",
                    result="fail",
                    message=(
                        f"assume_role_arn '{arn}' does not match the required ARN pattern. "
                        "Required: arn:aws:iam::<12-digit-account-id>:role/<role-name>. "
                        "Role name may contain: letters, digits, +=,.@_/- "
                        "Example: arn:aws:iam::123456789012:role/mif-glue-iceberg-role"
                    ),
                    field="assume_role_arn",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="SER-FULL-001",
                    rule_name="IAM Role ARN Full Validation",
                    result="pass",
                    message="assume_role_arn matches full ARN pattern \u2713",
                    field="assume_role_arn",
                ).model_dump())

        # SCHED-001: trigger_schedule — when non-empty must match cron(...) or rate(...)
        trigger = (state.get("trigger_schedule") or "").strip()
        _CRON_SAFE = re.compile(r"^cron\([0-9 *?,/\-]+\)$")
        _RATE_SAFE = re.compile(r"^rate\(\d+ (?:minute|hour|day)s?\)$")
        if trigger:
            if not (_CRON_SAFE.match(trigger) or _RATE_SAFE.match(trigger)):
                results.append(ValidationResult(
                    rule_id="SCHED-001",
                    rule_name="Trigger Schedule Character Safety",
                    result="fail",
                    message=(
                        f"trigger_schedule '{trigger}' does not match an allowed format. "
                        "Must be cron(minute hour day month day-of-week year) using only digits, "
                        "spaces, *, ?, /, ,, - "
                        "or rate(value unit). Examples: cron(0 1 * * ? *), rate(1 hour)"
                    ),
                    field="trigger_schedule",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="SCHED-001",
                    rule_name="Trigger Schedule Character Safety",
                    result="pass",
                    message=f"trigger_schedule '{trigger}' is structurally safe for HCL \u2713",
                    field="trigger_schedule",
                ).model_dump())

        return results

    # ── Version format validation ───────────────────────────────────────────────────────────────

    def _validate_versions(self, state: dict) -> list[dict]:
        """
        Format validation for version fields that have no allowlist but must be
        structurally safe for HCL interpolation.

        Rule IDs: JV-CHAR-001, GV-CHAR-001
        """
        results = []

        # JV-CHAR-001: job_version — semantic version X.Y.Z
        job_version = (state.get("job_version") or "").strip()
        _SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
        if job_version:
            if not _SEMVER.match(job_version):
                results.append(ValidationResult(
                    rule_id="JV-CHAR-001",
                    rule_name="Job Version Format",
                    result="fail",
                    message=(
                        f"job_version '{job_version}' is not a valid semantic version. "
                        "Must be X.Y.Z format (digits and dots only, three parts). "
                        "Example: 0.3.0"
                    ),
                    field="job_version",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="JV-CHAR-001",
                    rule_name="Job Version Format",
                    result="pass",
                    message=f"job_version '{job_version}' is valid semver \u2713",
                    field="job_version",
                ).model_dump())

        # GV-CHAR-001: glue_version — X.Y format (major.minor)
        glue_version = (state.get("glue_version") or "").strip()
        _GLUE_VER = re.compile(r"^\d+\.\d+$")
        if glue_version:
            if not _GLUE_VER.match(glue_version):
                results.append(ValidationResult(
                    rule_id="GV-CHAR-001",
                    rule_name="Glue Version Format",
                    result="fail",
                    message=(
                        f"glue_version '{glue_version}' is not a valid format. "
                        "Must be X.Y (major.minor, digits and one dot only). "
                        "Known values: 4.0, 5.0, 5.1"
                    ),
                    field="glue_version",
                ).model_dump())
            else:
                results.append(ValidationResult(
                    rule_id="GV-CHAR-001",
                    rule_name="Glue Version Format",
                    result="pass",
                    message=f"glue_version '{glue_version}' is valid format \u2713",
                    field="glue_version",
                ).model_dump())

        return results