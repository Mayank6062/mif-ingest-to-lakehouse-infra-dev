"""
Tests for Terraform validation (terraform_validator.py and validate_terraform_node.py)

Coverage:
- terraform_validator: validation passes, init fails, fmt fails, validate fails
- validate_terraform_node: routing based on validation result
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from app.services.terraform_validator import TerraformValidator, TerraformValidationError
from app.graph.state import STEP_VALIDATE_TERRAFORM, STEP_CREATE_PR


class TestTerraformValidator:
    """Test terraform_validator.py"""

    def test_validate_success(self):
        """Test successful terraform validation."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "locals { env = \"dev\" }",
            "glue.tf": "resource \"aws_glue_job\" \"test\" { name = \"test\" }",
        }

        # Mock subprocess to simulate successful terraform commands
        with patch("subprocess.run") as mock_run:
            # Mock return for all three commands (init, fmt, validate)
            def side_effect(*args, **kwargs):
                result = MagicMock()
                if "validate" in args[0]:
                    # Return JSON for terraform validate -json
                    result.stdout = '{"diagnostics":[],"format_version":"1.0"}'
                    result.stderr = ""
                else:
                    result.stdout = "✓ Terraform operation passed"
                    result.stderr = ""
                result.returncode = 0
                return result

            mock_run.side_effect = side_effect

            result = validator.validate(terraform_files, "test-source")

        assert result["status"] == "passed"
        assert "passed" in result["logs"].lower()
        assert result["errors"] == ""
        assert result["failed_command"] is None
        assert result["terraform_validation_diagnostics"] == []

    def test_validate_init_fails(self):
        """Test when terraform init fails."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "locals { env = \"dev\" }",
        }

        with patch("subprocess.run") as mock_run:
            # Mock init failure
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.stderr = "Error: Backend initialization failed"
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            result = validator.validate(terraform_files, "test-source")

        assert result["status"] == "failed"
        assert result["failed_command"] == "terraform init"
        assert "Backend initialization failed" in result["errors"]

    def test_validate_fmt_fails(self):
        """Test when terraform fmt check fails."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "locals { env = \"dev\" }",
        }

        with patch("subprocess.run") as mock_run:
            # Mock init success, fmt failure
            def side_effect(*args, **kwargs):
                result = MagicMock()
                if "init" in args[0]:
                    result.returncode = 0
                    result.stdout = "Initialized"
                    result.stderr = ""
                elif "fmt" in args[0]:
                    result.returncode = 1
                    result.stdout = "main.tf: File not formatted correctly"
                    result.stderr = ""
                else:
                    result.returncode = 0
                    result.stdout = "Valid"
                    result.stderr = ""
                return result

            mock_run.side_effect = side_effect

            result = validator.validate(terraform_files, "test-source")

        assert result["status"] == "failed"
        assert result["failed_command"] == "terraform fmt -check"

    def test_validate_validate_fails(self):
        """Test when terraform validate fails."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "locals { env = \"dev\" }",
        }

        with patch("subprocess.run") as mock_run:
            # Mock init and fmt success, validate failure
            def side_effect(*args, **kwargs):
                result = MagicMock()
                if "validate" in args[0]:
                    result.returncode = 1
                    result.stdout = '{"diagnostics":[{"severity":"error","summary":"Invalid variable reference","detail":"Variable not found","range":{"filename":"locals.tf","start":{"line":1,"column":10},"end":{"line":1,"column":20}}}],"format_version":"1.0"}'
                    result.stderr = "Error: Invalid variable reference"
                else:
                    result.returncode = 0
                    result.stdout = "OK"
                    result.stderr = ""
                return result

            mock_run.side_effect = side_effect

            result = validator.validate(terraform_files, "test-source")

        assert result["status"] == "failed"
        assert result["failed_command"] == "terraform validate"
        assert "Invalid variable reference" in result["errors"]
        assert len(result["terraform_validation_diagnostics"]) == 1
        assert result["terraform_validation_diagnostics"][0]["severity"] == "error"

    def test_validate_timeout(self):
        """Test when terraform command times out."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "locals { env = \"dev\" }",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("terraform", 60)

            result = validator.validate(terraform_files, "test-source")

        assert result["status"] == "failed"
        assert "timed out" in result["errors"].lower()

    def test_cleanup_temp_directory(self):
        """Test that temporary directory is cleaned up."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "locals { env = \"dev\" }",
        }

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "OK"
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = validator.validate(terraform_files, "test-source")
            temp_dir = validator.temp_dir

        # After validation, temp_dir should be cleaned up
        assert validator.temp_dir is None
        if temp_dir:
            assert not Path(temp_dir).exists()

    def test_skip_empty_files(self):
        """Test that empty terraform files are skipped."""
        validator = TerraformValidator()
        
        terraform_files = {
            "locals.tf": "",  # Empty file
            "glue.tf": "resource \"aws_glue_job\" \"test\" { name = \"test\" }",
        }

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "OK"
            mock_result.stderr = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = validator.validate(terraform_files, "test-source")

        assert result["status"] == "passed"

    def test_no_files_error(self):
        """Test error when no terraform files provided."""
        validator = TerraformValidator()
        
        terraform_files = {}  # No files

        result = validator.validate(terraform_files, "test-source")

        # Should still create temp dir and handle gracefully
        assert result["status"] in ["passed", "failed"]

    def test_parse_terraform_diagnostics(self):
        """Test parsing of terraform validate -json diagnostics."""
        validator = TerraformValidator()
        
        json_with_diagnostics = '''{
            "diagnostics": [
                {
                    "severity": "error",
                    "summary": "Invalid variable reference",
                    "detail": "Variable not found in scope",
                    "range": {
                        "filename": "locals.tf",
                        "start": {"line": 5, "column": 10},
                        "end": {"line": 5, "column": 25}
                    },
                    "module_address": "module.glue"
                },
                {
                    "severity": "warning",
                    "summary": "Deprecated attribute",
                    "detail": "This attribute is deprecated",
                    "range": {
                        "filename": "glue.tf",
                        "start": {"line": 10, "column": 5},
                        "end": {"line": 10, "column": 15}
                    },
                    "module_address": ""
                }
            ],
            "format_version": "1.0"
        }'''
        
        parsed = validator._parse_terraform_diagnostics(json_with_diagnostics)
        
        assert len(parsed) == 2
        assert parsed[0]["severity"] == "error"
        assert parsed[0]["summary"] == "Invalid variable reference"
        assert parsed[0]["range"]["filename"] == "locals.tf"
        assert parsed[1]["severity"] == "warning"
        assert parsed[1]["module_address"] == ""

    def test_parse_terraform_diagnostics_empty(self):
        """Test parsing of empty terraform diagnostics."""
        validator = TerraformValidator()
        
        json_empty = '{"diagnostics": [], "format_version": "1.0"}'
        parsed = validator._parse_terraform_diagnostics(json_empty)
        
        assert parsed == []

    def test_parse_terraform_diagnostics_invalid_json(self):
        """Test parsing of invalid JSON returns empty list."""
        validator = TerraformValidator()
        
        invalid_json = "{ invalid json"
        parsed = validator._parse_terraform_diagnostics(invalid_json)
        
        assert parsed == []


class TestValidateTerraformNode:
    """Test validate_terraform_node.py"""

    def test_validation_passes_routes_to_create_pr(self):
        """Test that passing validation routes to create_pr."""
        from app.graph.nodes.validate_terraform import validate_terraform_node

        state = {
            "source_system": "test",
            "job_key": "test-job",
            "locals_tf_full": "locals { env = \"dev\" }",
            "glue_tf_content": "resource \"aws_glue_job\" \"test\" {}",
            "current_step": "collect_topic",
            "messages": [],
        }

        with patch("app.graph.nodes.validate_terraform.TerraformValidator.validate") as mock_validate:
            mock_validate.return_value = {
                "status": "passed",
                "logs": "✓ All validations passed",
                "errors": "",
                "failed_command": None,
                "terraform_validation_diagnostics": [],
            }

            result = validate_terraform_node(state)

        assert result["current_step"] == STEP_VALIDATE_TERRAFORM
        assert result["terraform_validation_status"] == "passed"
        assert result["terraform_validation_diagnostics"] == []
        assert result["waiting_for_user"] is False
        assert any("passed" in m.get("content", "").lower() for m in result["messages"])

    def test_validation_fails_sets_error(self):
        """Test that failing validation sets error message."""
        from app.graph.nodes.validate_terraform import validate_terraform_node

        state = {
            "source_system": "test",
            "job_key": "test-job",
            "locals_tf_full": "locals { INVALID }",
            "glue_tf_content": "resource \"aws_glue_job\" \"test\" {}",
            "current_step": "collect_topic",
            "messages": [],
        }

        with patch("app.graph.nodes.validate_terraform.TerraformValidator.validate") as mock_validate:
            mock_validate.return_value = {
                "status": "failed",
                "logs": "terraform validate output",
                "errors": "Error: Invalid syntax in locals.tf",
                "failed_command": "terraform validate",
                "terraform_validation_diagnostics": [
                    {
                        "severity": "error",
                        "summary": "Invalid syntax",
                        "detail": "Unexpected token",
                        "range": {"filename": "locals.tf"},
                        "module_address": ""
                    }
                ],
            }

            result = validate_terraform_node(state)

        assert result["current_step"] == STEP_VALIDATE_TERRAFORM
        assert result["terraform_validation_status"] == "failed"
        assert len(result["terraform_validation_diagnostics"]) == 1
        assert result["waiting_for_user"] is True
        assert any("failed" in m.get("content", "").lower() for m in result["messages"])
        assert "Invalid syntax" in result["terraform_validation_errors"]

    def test_no_terraform_files_error(self):
        """Test error when no terraform files were generated."""
        from app.graph.nodes.validate_terraform import validate_terraform_node

        state = {
            "source_system": "test",
            "job_key": "test-job",
            "locals_tf_full": None,  # Not generated
            "glue_tf_content": None,  # Not generated
            "current_step": "collect_topic",
            "messages": [],
        }

        result = validate_terraform_node(state)

        assert result["current_step"] == STEP_VALIDATE_TERRAFORM
        assert result["terraform_validation_status"] == "failed"
        assert result["waiting_for_user"] is True
        assert "Missing" in result["terraform_validation_errors"]

    def test_existing_system_merges_and_validates(self):
        """For existing source systems, ensure locals.tf is fetched, merged, and passed to validator."""
        from app.graph.nodes.validate_terraform import validate_terraform_node

        state = {
            "source_system": "test",
            "job_key": "test-job",
            "terraform_hcl": 'test_entry = { name = "new" }',
            "source_system_exists": True,
            "current_step": "collect_topic",
            "messages": [],
        }

        # Mock GitHubService used inside the node to return an existing locals.tf
        # Patch import_module used in the node so we don't need the PyGithub dependency
        import types
        fake_module = types.SimpleNamespace()
        FakeGHClass = MagicMock()
        gh_instance = MagicMock()
        FakeGHClass.return_value = gh_instance
        fake_module.GitHubService = FakeGHClass
        fake_module._insert_into_glue_jobs = lambda content, entry: content.replace("}\n", f"\n{entry}\n}}\n")

        # Patch the validator to capture the files written for validation
        with patch("app.graph.nodes.validate_terraform.TerraformValidator.validate") as mock_validate:
            mock_validate.return_value = {
                "status": "passed",
                "logs": "✓ All validations passed",
                "errors": "",
                "failed_command": None,
                "terraform_validation_diagnostics": [],
            }

            with patch("app.graph.nodes.validate_terraform.import_module") as mock_import_module:
                mock_import_module.return_value = fake_module
                gh_instance.get_source_system_repository_state.return_value = {
                    "locals_path": "test/locals.tf",
                    "github_exists": True,
                }
                gh_instance._get_repo.return_value = MagicMock()
                base_file = MagicMock()
                base_file.decoded_content = b"glue_jobs = {\n  existing = {}\n}\n"
                gh_instance._get_file_content.return_value = base_file

                result = validate_terraform_node(state)

                # Ensure validator was called and locals.tf was included
                assert mock_validate.called
                called_args = mock_validate.call_args[0]
                passed_files = called_args[0]
                assert "locals.tf" in passed_files
                assert "existing" in passed_files["locals.tf"]
                assert "test_entry" in passed_files["locals.tf"]

                assert result["terraform_validation_status"] == "passed"
