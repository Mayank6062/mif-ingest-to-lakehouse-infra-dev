"""
Unit tests for SEC-004 HCL injection security fixes.

Covers:
  escape_hcl_string    HCL string escaping function (terraform_agent.py)
  DBR-CHAR-001         Iceberg database character safety
  SWR-CHAR-001         Iceberg warehouse URL safety
  SER-FULL-001         IAM role ARN full pattern validation
  SCHED-001            Trigger schedule character safety
  JV-CHAR-001          Job version semver format
  GV-CHAR-001          Glue version format
  SGR-001              Subgroup promoted to FAIL severity
"""

import pytest
from app.agents.terraform_agent import escape_hcl_string


# ── Helpers ───────────────────────────────────────────────────────────────────

def _agent():
    """Return a ValidationAgent backed by the real KnowledgeBase."""
    from app.agents.validation_agent import ValidationAgent
    return ValidationAgent()


def _result(results: list[dict], rule_id: str) -> dict | None:
    return next((r for r in results if r["rule_id"] == rule_id), None)


def _base_state(**overrides):
    """Minimal fully-valid state used by validate_all integration tests."""
    state = {
        "topic": "dev.saptcc.multi-1.raw",
        "environment": "dev",
        "source_system": "saptcc",
        "schema_grain": "multi-1",
        "job_key": "kafka-to-iceberg-batch-saptcc-multi-1",
        "iceberg_database": "minerva_dev_src_agtr_saptcc_prd_raw_db",
        "iceberg_warehouse": "s3://minerva-dev-src-agtr/current/prd/raw/sap_tce/",
        "assume_role_arn": "arn:aws:iam::123456789012:role/mif-glue-iceberg-role",
        "worker_type": "G.1X",
        "number_of_workers": 2,
        "job_type": "unified",
        "job_version": "0.3.0",
        "glue_version": "5.1",
        "ent_func": "AGTR",
        "subgroup": "apac",
        "scheduling_mode": "manual",
        "trigger_schedule": None,
    }
    state.update(overrides)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# escape_hcl_string
# ─────────────────────────────────────────────────────────────────────────────

class TestEscapeHclString:
    def test_plain_string_unchanged(self):
        assert escape_hcl_string("hello_world") == "hello_world"

    def test_empty_string_unchanged(self):
        assert escape_hcl_string("") == ""

    def test_backslash_escaped(self):
        # Single backslash → double backslash
        assert escape_hcl_string("path\\file") == "path\\\\file"

    def test_double_quote_escaped(self):
        result = escape_hcl_string('say "hello"')
        assert result == 'say \\"hello\\"'

    def test_newline_escaped(self):
        result = escape_hcl_string("line1\nline2")
        assert result == "line1\\nline2"
        assert "\n" not in result

    def test_carriage_return_escaped(self):
        result = escape_hcl_string("line1\rline2")
        assert result == "line1\\rline2"
        assert "\r" not in result

    def test_terraform_interpolation_escaped(self):
        # ${...} sequences must become $${...} to prevent Terraform interpolation
        result = escape_hcl_string("${file('/etc/passwd')}")
        assert result == "$${file('/etc/passwd')}"
        assert "${" not in result

    def test_terraform_directive_escaped(self):
        result = escape_hcl_string("%{if true}inject%{endif}")
        assert result == "%%{if true}inject%%{endif}"
        assert "%{" not in result

    def test_backslash_escaped_before_quote(self):
        # Backslash MUST be escaped before quote to avoid \" becoming \\"
        # Input: one backslash followed by a quote: \"
        result = escape_hcl_string('\\"')
        # Step 1: \ → \\  →  \\"
        # Step 2: " → \"  →  \\\\"
        assert result == '\\\\\\"'

    def test_injection_attempt_neutralised(self):
        # Simulate a real injection payload targeting HCL string context
        payload = 'legit_db"\n  "--injected" = "evil'
        result = escape_hcl_string(payload)
        # No literal newline in output
        assert "\n" not in result
        # No unescaped quote that could break the HCL string boundary
        # (every " is preceded by \)
        import re
        unescaped_quotes = re.findall(r'(?<!\\)"', result)
        assert unescaped_quotes == [], f"Unescaped quotes found: {unescaped_quotes}"

    def test_s3_url_safe_and_unchanged(self):
        url = "s3://bucket/path/to/folder/"
        assert escape_hcl_string(url) == url

    def test_arn_safe_and_unchanged(self):
        arn = "arn:aws:iam::123456789012:role/mif-glue-iceberg-role"
        assert escape_hcl_string(arn) == arn

    def test_cron_safe_and_unchanged(self):
        cron = "cron(0 1 * * ? *)"
        assert escape_hcl_string(cron) == cron

    def test_semver_safe_and_unchanged(self):
        assert escape_hcl_string("0.3.0") == "0.3.0"

    def test_glue_version_safe_and_unchanged(self):
        assert escape_hcl_string("5.1") == "5.1"


# ─────────────────────────────────────────────────────────────────────────────
# SCHED-001  Trigger schedule character safety
# ─────────────────────────────────────────────────────────────────────────────

class TestSCHED001:
    def _run(self, trigger):
        return _agent()._validate_hcl_safe_fields({"trigger_schedule": trigger})

    def test_valid_cron_6_fields_passes(self):
        r = _result(self._run("cron(0 1 * * ? *)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_cron_with_numbers_passes(self):
        r = _result(self._run("cron(0 5 15 * ? 2025)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_rate_hour_passes(self):
        r = _result(self._run("rate(1 hour)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_rate_minutes_plural_passes(self):
        r = _result(self._run("rate(30 minutes)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_rate_days_passes(self):
        r = _result(self._run("rate(7 days)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_injection_with_quote_and_newline_fails(self):
        r = _result(self._run('cron(0 5 * * ? *)"\nmalicious'), "SCHED-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_terraform_interpolation_in_cron_fails(self):
        r = _result(self._run("cron(${file('/etc/passwd')} 5 * * ? *)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_arbitrary_text_fails(self):
        r = _result(self._run("every day at midnight"), "SCHED-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_empty_trigger_produces_no_result(self):
        r = _result(self._run(""), "SCHED-001")
        assert r is None  # empty = not validated, not an error

    def test_none_trigger_produces_no_result(self):
        r = _result(self._run(None), "SCHED-001")
        assert r is None

    def test_cron_with_backslash_fails(self):
        r = _result(self._run("cron(0 5 * * ? \\*)"), "SCHED-001")
        assert r is not None
        assert r["result"] == "fail"


# ─────────────────────────────────────────────────────────────────────────────
# SER-FULL-001  IAM role ARN full pattern validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSERFULL001:
    def _run(self, arn):
        return _agent()._validate_hcl_safe_fields({"assume_role_arn": arn})

    def test_valid_arn_passes(self):
        r = _result(self._run("arn:aws:iam::123456789012:role/mif-glue-iceberg-role"), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_arn_with_path_passes(self):
        r = _result(self._run("arn:aws:iam::123456789012:role/path/sub/my-role"), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_arn_with_special_chars_in_role_passes(self):
        r = _result(self._run("arn:aws:iam::123456789012:role/role@name+test=1"), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_injection_via_quote_in_role_name_fails(self):
        r = _result(self._run('arn:aws:iam::123456789012:role/role"\ninjected'), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_wrong_prefix_fails(self):
        r = _result(self._run("not-an-arn"), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_non_12_digit_account_id_fails(self):
        r = _result(self._run("arn:aws:iam::12345:role/my-role"), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_terraform_interpolation_in_arn_fails(self):
        r = _result(self._run("arn:aws:iam::${evil}:role/x"), "SER-FULL-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_empty_arn_produces_no_result(self):
        r = _result(self._run(""), "SER-FULL-001")
        assert r is None

    def test_placeholder_fails_arn_safety(self):
        # <AWS_ACCOUNT_ID_REQUIRED> contains < and > which fail the regex
        r = _result(
            self._run("arn:aws:iam::<AWS_ACCOUNT_ID_REQUIRED>:role/x"),
            "SER-FULL-001",
        )
        # placeholder check is skipped; the < > chars fail the regex
        assert r is not None
        assert r["result"] == "fail"


# ─────────────────────────────────────────────────────────────────────────────
# JV-CHAR-001  Job version semver format
# ─────────────────────────────────────────────────────────────────────────────

class TestJVCHAR001:
    def _run(self, version):
        return _agent()._validate_versions({"job_version": version})

    def test_valid_semver_passes(self):
        r = _result(self._run("0.3.0"), "JV-CHAR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_another_valid_semver_passes(self):
        r = _result(self._run("1.10.3"), "JV-CHAR-001")
        assert r["result"] == "pass"

    def test_injection_with_quote_newline_fails(self):
        r = _result(self._run('0.3.0"\ninjected = "evil'), "JV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_missing_patch_segment_fails(self):
        r = _result(self._run("0.3"), "JV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_text_version_fails(self):
        r = _result(self._run("latest"), "JV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_version_with_v_prefix_fails(self):
        r = _result(self._run("v0.3.0"), "JV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_empty_produces_no_result(self):
        r = _result(self._run(""), "JV-CHAR-001")
        assert r is None


# ─────────────────────────────────────────────────────────────────────────────
# GV-CHAR-001  Glue version format
# ─────────────────────────────────────────────────────────────────────────────

class TestGVCHAR001:
    def _run(self, version):
        return _agent()._validate_versions({"glue_version": version})

    def test_valid_5_1_passes(self):
        r = _result(self._run("5.1"), "GV-CHAR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_4_0_passes(self):
        r = _result(self._run("4.0"), "GV-CHAR-001")
        assert r["result"] == "pass"

    def test_valid_5_0_passes(self):
        r = _result(self._run("5.0"), "GV-CHAR-001")
        assert r["result"] == "pass"

    def test_injection_with_quote_newline_fails(self):
        r = _result(self._run('5.1"\ninjected'), "GV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_three_part_semver_fails(self):
        # Glue version is X.Y not X.Y.Z
        r = _result(self._run("5.1.0"), "GV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_text_fails(self):
        r = _result(self._run("latest"), "GV-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_empty_produces_no_result(self):
        r = _result(self._run(""), "GV-CHAR-001")
        assert r is None


# ─────────────────────────────────────────────────────────────────────────────
# SGR-001  Subgroup promoted from WARN to FAIL
# ─────────────────────────────────────────────────────────────────────────────

class TestSGR001Fail:
    def _run(self, subgroup):
        return _agent()._validate_subgroup({"subgroup": subgroup})

    def test_valid_apac_passes(self):
        r = _result(self._run("apac"), "SGR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_na_passes(self):
        r = _result(self._run("na"), "SGR-001")
        assert r["result"] == "pass"

    def test_valid_latam_passes(self):
        r = _result(self._run("latam"), "SGR-001")
        assert r["result"] == "pass"

    def test_unknown_subgroup_fails_not_warns(self):
        r = _result(self._run("eu"), "SGR-001")
        assert r is not None
        assert r["result"] == "fail", "SGR-001 must now be FAIL (not warn) for unknown subgroup"

    def test_empty_subgroup_fails_not_warns(self):
        r = _result(self._run(""), "SGR-001")
        assert r is not None
        assert r["result"] == "fail", "SGR-001 must now be FAIL (not warn) for empty subgroup"

    def test_injection_attempt_fails(self):
        r = _result(self._run('apac"\ninjected'), "SGR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_has_failures_true_for_unknown_subgroup(self):
        agent = _agent()
        state = _base_state(subgroup="invalid-region")
        results = agent.validate_all(state)
        assert agent.has_failures(results), (
            "validate_all must report has_failures=True when subgroup is invalid"
        )

    def test_has_failures_false_for_valid_subgroup(self):
        agent = _agent()
        state = _base_state(subgroup="apac")
        results = agent.validate_all(state)
        sgr = _result(results, "SGR-001")
        assert sgr is not None
        assert sgr["result"] == "pass"


# ─────────────────────────────────────────────────────────────────────────────
# DBR-CHAR-001  Iceberg database character safety
# ─────────────────────────────────────────────────────────────────────────────

class TestDBRCHAR001:
    def _run(self, db):
        return _agent()._validate_hcl_safe_fields({"iceberg_database": db})

    def test_valid_underscore_name_passes(self):
        r = _result(self._run("minerva_dev_src_agtr_saptcc_prd_raw_db"), "DBR-CHAR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_valid_hyphen_name_passes(self):
        r = _result(self._run("my-database-raw"), "DBR-CHAR-001")
        assert r["result"] == "pass"

    def test_quote_injection_fails(self):
        r = _result(self._run('my_db"\n--injected'), "DBR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_space_in_name_fails(self):
        r = _result(self._run("my db"), "DBR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_terraform_interpolation_fails(self):
        r = _result(self._run("${local.env}_db"), "DBR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_empty_produces_no_result(self):
        r = _result(self._run(""), "DBR-CHAR-001")
        assert r is None


# ─────────────────────────────────────────────────────────────────────────────
# SWR-CHAR-001  Iceberg warehouse URL safety
# ─────────────────────────────────────────────────────────────────────────────

class TestSWRCHAR001:
    def _run(self, warehouse):
        return _agent()._validate_hcl_safe_fields({"iceberg_warehouse": warehouse})

    def test_valid_s3_url_passes(self):
        r = _result(
            self._run("s3://minerva-dev-src-agtr/current/prd/raw/sap_tce/"),
            "SWR-CHAR-001",
        )
        assert r is not None
        assert r["result"] == "pass"

    def test_quote_injection_via_s3_path_fails(self):
        r = _result(self._run('s3://legit/path/"\ninjected'), "SWR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_missing_trailing_slash_fails(self):
        r = _result(self._run("s3://bucket/path"), "SWR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_http_scheme_fails(self):
        r = _result(self._run("http://bucket/path/"), "SWR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_terraform_interpolation_in_bucket_fails(self):
        r = _result(self._run("s3://${evil}/path/"), "SWR-CHAR-001")
        assert r is not None
        assert r["result"] == "fail"

    def test_empty_produces_no_result(self):
        r = _result(self._run(""), "SWR-CHAR-001")
        assert r is None


# ─────────────────────────────────────────────────────────────────────────────
# Integration: validate_all blocks on injection attempts
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateAllIntegration:
    def test_clean_state_has_no_failures(self):
        agent = _agent()
        results = agent.validate_all(_base_state())
        assert not agent.has_failures(results), "Clean valid state must pass all rules"

    def test_injection_in_iceberg_database_blocked(self):
        agent = _agent()
        state = _base_state(iceberg_database='minerva_dev_raw_db"\ninjected')
        results = agent.validate_all(state)
        assert agent.has_failures(results)
        r = _result(results, "DBR-CHAR-001")
        assert r is not None and r["result"] == "fail"

    def test_injection_in_warehouse_blocked(self):
        agent = _agent()
        state = _base_state(iceberg_warehouse='s3://legit/path/"\ninjected/')
        results = agent.validate_all(state)
        assert agent.has_failures(results)
        r = _result(results, "SWR-CHAR-001")
        assert r is not None and r["result"] == "fail"

    def test_injection_in_trigger_schedule_blocked(self):
        agent = _agent()
        state = _base_state(
            scheduling_mode="scheduled",
            trigger_schedule='cron(0 5 * * ? *)"\nmalicious',
        )
        results = agent.validate_all(state)
        assert agent.has_failures(results)
        r = _result(results, "SCHED-001")
        assert r is not None and r["result"] == "fail"

    def test_bad_job_version_blocked(self):
        agent = _agent()
        state = _base_state(job_version='0.3.0"\ninjected')
        results = agent.validate_all(state)
        assert agent.has_failures(results)
        r = _result(results, "JV-CHAR-001")
        assert r is not None and r["result"] == "fail"

    def test_bad_glue_version_blocked(self):
        agent = _agent()
        state = _base_state(glue_version='5.1"\ninjected')
        results = agent.validate_all(state)
        assert agent.has_failures(results)
        r = _result(results, "GV-CHAR-001")
        assert r is not None and r["result"] == "fail"

    def test_arn_without_prefix_now_fails(self):
        # SER-001 promoted from warn to fail
        agent = _agent()
        state = _base_state(assume_role_arn="not-an-arn")
        results = agent.validate_all(state)
        assert agent.has_failures(results)
        r = _result(results, "SER-001")
        assert r is not None and r["result"] == "fail"
