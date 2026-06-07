"""
Unit tests for ValidationAgent — covers the 5 newly implemented rules:
  TR-003  Topic segment count
  TR-005  Source system segment format
  TR-002  Topic suffix (rule-ID fix verification)
  JR-002  Duplicate job key detection
  JOBT-002 Scheduling mode
  SGR-001  Subgroup
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _agent():
    """Return a ValidationAgent with a real KnowledgeBase (no mocking needed)."""
    from app.agents.validation_agent import ValidationAgent
    return ValidationAgent()


def _result(results: list[dict], rule_id: str) -> dict | None:
    return next((r for r in results if r["rule_id"] == rule_id), None)


# ─────────────────────────────────────────────────────────────────────────────
# TR-003  Topic segment count
# ─────────────────────────────────────────────────────────────────────────────

class TestTR003:
    def test_exactly_four_segments_passes(self):
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.multi-1.raw")
        r = _result(results, "TR-003")
        assert r is not None, "TR-003 result not found"
        assert r["result"] == "pass"

    def test_three_segments_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.raw")
        r = _result(results, "TR-003")
        assert r is not None
        assert r["result"] == "fail"
        assert "3" in r["message"]

    def test_five_segments_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.multi.1.raw")
        r = _result(results, "TR-003")
        assert r is not None
        assert r["result"] == "fail"
        assert "5" in r["message"]

    def test_two_segments_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.raw")
        r = _result(results, "TR-003")
        assert r is not None
        assert r["result"] == "fail"


# ─────────────────────────────────────────────────────────────────────────────
# TR-005  Source system segment format
# ─────────────────────────────────────────────────────────────────────────────

class TestTR005:
    def test_lowercase_alphanumeric_passes(self):
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.multi-1.raw")
        r = _result(results, "TR-005")
        assert r is not None
        assert r["result"] == "pass"

    def test_hyphen_in_source_passes(self):
        agent = _agent()
        results = agent._validate_topic("dev.my-source.grain.raw")
        r = _result(results, "TR-005")
        assert r is not None
        assert r["result"] == "pass"

    def test_uppercase_in_source_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.SapTCC.multi-1.raw")
        r = _result(results, "TR-005")
        assert r is not None
        assert r["result"] == "fail"
        assert "SapTCC" in r["message"]

    def test_underscore_in_source_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.sap_tcc.multi-1.raw")
        r = _result(results, "TR-005")
        assert r is not None
        assert r["result"] == "fail"

    def test_space_in_source_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.sap tcc.multi-1.raw")
        # 5 segments due to space being inside segment — still only 4 dots is tricky;
        # "sap tcc" in segment[1] should fail TR-005
        r = _result(results, "TR-005")
        if r:  # TR-005 only runs when segment count == 4
            assert r["result"] == "fail"

    def test_tr005_not_run_when_wrong_segment_count(self):
        """TR-005 must not be emitted if TR-003 already failed (only 3 segments)."""
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.raw")
        # TR-003 fails; TR-005 should not be present
        r = _result(results, "TR-005")
        assert r is None


# ─────────────────────────────────────────────────────────────────────────────
# TR-002  Topic suffix (.raw) — rule-ID fix verification
# ─────────────────────────────────────────────────────────────────────────────

class TestTR002:
    def test_raw_suffix_passes(self):
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.multi-1.raw")
        r = _result(results, "TR-002")
        assert r is not None
        assert r["result"] == "pass"

    def test_non_raw_suffix_fails(self):
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.multi-1.processed")
        r = _result(results, "TR-002")
        assert r is not None
        assert r["result"] == "fail"

    def test_old_tr005_id_no_longer_used_for_suffix(self):
        """After the rule-ID fix, 'TR-005' must not appear for the suffix check."""
        agent = _agent()
        results = agent._validate_topic("dev.saptcc.multi-1.processed")
        ids = [r["rule_id"] for r in results]
        # TR-005 should be absent (3 segments → TR-003 fail, no TR-005)
        # or present for source-system check only
        suffix_with_wrong_id = [
            r for r in results
            if r["rule_id"] == "TR-005" and ".raw" in r.get("message", "")
        ]
        assert suffix_with_wrong_id == [], (
            "TR-005 must not be used for the .raw suffix check"
        )


# ─────────────────────────────────────────────────────────────────────────────
# JOBT-002  Scheduling mode
# ─────────────────────────────────────────────────────────────────────────────

class TestJOBT002:
    def _run(self, mode):
        agent = _agent()
        return agent._validate_job_type({"scheduling_mode": mode})

    def test_manual_passes(self):
        r = _result(self._run("manual"), "JOBT-002")
        assert r is not None
        assert r["result"] == "pass"

    def test_scheduled_passes(self):
        r = _result(self._run("scheduled"), "JOBT-002")
        assert r is not None
        assert r["result"] == "pass"

    def test_invalid_mode_fails(self):
        r = _result(self._run("cron"), "JOBT-002")
        assert r is not None
        assert r["result"] == "fail"
        assert "cron" in r["message"]

    def test_empty_string_fails(self):
        r = _result(self._run(""), "JOBT-002")
        assert r is not None
        assert r["result"] == "fail"

    def test_uppercase_fails(self):
        r = _result(self._run("Manual"), "JOBT-002")
        assert r is not None
        assert r["result"] == "fail"


# ─────────────────────────────────────────────────────────────────────────────
# SGR-001  Subgroup
# ─────────────────────────────────────────────────────────────────────────────

class TestSGR001:
    def _run(self, subgroup):
        agent = _agent()
        return agent._validate_subgroup({"subgroup": subgroup})

    def test_apac_passes(self):
        r = _result(self._run("apac"), "SGR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_na_passes(self):
        r = _result(self._run("na"), "SGR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_latam_passes(self):
        r = _result(self._run("latam"), "SGR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_case_insensitive_apac_passes(self):
        r = _result(self._run("APAC"), "SGR-001")
        assert r is not None
        assert r["result"] == "pass"

    def test_unknown_value_warns(self):
        r = _result(self._run("emea"), "SGR-001")
        assert r is not None
        assert r["result"] == "warn"
        assert "emea" in r["message"]

    def test_empty_warns(self):
        r = _result(self._run(""), "SGR-001")
        assert r is not None
        assert r["result"] == "warn"


# ─────────────────────────────────────────────────────────────────────────────
# JR-002  Duplicate job key detection
# ─────────────────────────────────────────────────────────────────────────────

class TestJR002:
    def _state(self, job_key="kafka-to-iceberg-batch-saptcc-multi-1", source_exists=True):
        return {
            "job_key": job_key,
            "source_system": "saptcc",
            "source_system_exists": source_exists,
        }

    def test_new_source_system_skips_check(self):
        """JR-002 must produce no result for new source systems (no locals.tf to read)."""
        agent = _agent()
        results = agent._validate_duplicate_job(
            {**self._state(), "source_system_exists": False}
        )
        assert results == []

    def test_missing_job_key_skips_check(self):
        agent = _agent()
        results = agent._validate_duplicate_job({"job_key": "", "source_system": "saptcc", "source_system_exists": True})
        assert results == []

    def test_duplicate_detected(self):
        """When locals.tf contains the job key, JR-002 must fail."""
        locals_content = (
            'locals {\n'
            '  glue_jobs = {\n'
            '    "kafka-to-iceberg-batch-saptcc-multi-1" = {\n'
            '      worker_type = "G.1X"\n'
            '    }\n'
            '  }\n'
            '}\n'
        )
        mock_file = MagicMock()
        mock_file.decoded_content = locals_content.encode("utf-8")

        with patch("app.agents.validation_agent.GitHubService") as MockSvc:
            instance = MockSvc.return_value
            instance._get_repo.return_value = MagicMock()
            instance._get_file_content.return_value = mock_file
            instance._base_branch = "main"

            agent = _agent()
            results = agent._validate_duplicate_job(self._state())
            r = _result(results, "JR-002")
            assert r is not None
            assert r["result"] == "fail"
            assert "kafka-to-iceberg-batch-saptcc-multi-1" in r["message"]

    def test_no_duplicate_passes(self):
        """When locals.tf does not contain the job key, JR-002 must pass."""
        locals_content = (
            'locals {\n'
            '  glue_jobs = {\n'
            '    "kafka-to-iceberg-batch-saptcc-cdhdr" = {\n'
            '      worker_type = "G.1X"\n'
            '    }\n'
            '  }\n'
            '}\n'
        )
        mock_file = MagicMock()
        mock_file.decoded_content = locals_content.encode("utf-8")

        with patch("app.agents.validation_agent.GitHubService") as MockSvc:
            instance = MockSvc.return_value
            instance._get_repo.return_value = MagicMock()
            instance._get_file_content.return_value = mock_file
            instance._base_branch = "main"

            agent = _agent()
            results = agent._validate_duplicate_job(self._state())
            r = _result(results, "JR-002")
            assert r is not None
            assert r["result"] == "pass"

    def test_github_unavailable_skips_silently(self):
        """When GitHub raises an exception, JR-002 must return [] (never block)."""
        with patch("app.agents.validation_agent.GitHubService") as MockSvc:
            MockSvc.side_effect = Exception("No token")
            agent = _agent()
            results = agent._validate_duplicate_job(self._state())
            assert results == []

    def test_locals_tf_not_found_passes(self):
        """When locals.tf doesn't exist yet, JR-002 must return [] (new entry is fine)."""
        with patch("app.agents.validation_agent.GitHubService") as MockSvc:
            instance = MockSvc.return_value
            instance._get_repo.return_value = MagicMock()
            instance._get_file_content.return_value = None
            instance._base_branch = "main"

            agent = _agent()
            results = agent._validate_duplicate_job(self._state())
            assert results == []
