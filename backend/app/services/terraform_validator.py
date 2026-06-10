"""
Terraform validation service.
Runs terraform init, fmt, and validate on generated Terraform configuration.
Creates temporary working directory, captures all output/errors, and cleans up.
"""

import os
import subprocess
import tempfile
import shutil
import json
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class TerraformValidationError(Exception):
    """Raised when Terraform validation fails."""
    pass


class TerraformValidator:
    """Validates generated Terraform configuration."""

    def __init__(self):
        """Initialize validator."""
        self.temp_dir: Optional[str] = None

    def _create_temp_directory(self) -> str:
        """Create a temporary working directory for Terraform validation."""
        try:
            # Create a temp directory with a descriptive name
            self.temp_dir = tempfile.mkdtemp(prefix="terraform-validation-")
            logger.info(f"Created temporary validation directory: {self.temp_dir}")
            return self.temp_dir
        except Exception as e:
            logger.error(f"Failed to create temporary directory: {e}")
            raise TerraformValidationError(f"Cannot create temp directory: {e}")

    def _cleanup_temp_directory(self) -> None:
        """Remove the temporary working directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {self.temp_dir}: {e}")
        self.temp_dir = None

    def _write_terraform_files(self, work_dir: str, terraform_files: Dict[str, str]) -> None:
        """
        Write Terraform files to the working directory.

        Args:
            work_dir: Working directory path
            terraform_files: Dict of {filename: content}
                Expected keys: 'locals.tf', 'glue.tf' (at minimum)
        """
        try:
            for filename, content in terraform_files.items():
                if not content:
                    logger.debug(f"Skipping empty file: {filename}")
                    continue

                file_path = Path(work_dir) / filename
                file_path.write_text(content)
                logger.debug(f"Wrote Terraform file: {filename} ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"Failed to write Terraform files: {e}")
            raise TerraformValidationError(f"Cannot write Terraform files: {e}")

    def _run_command(self, command: list[str], work_dir: str, description: str) -> tuple[str, str, int]:
        """
        Run a shell command and capture stdout/stderr.

        Args:
            command: Command list to execute (e.g., ['terraform', 'init', '-backend=false'])
            work_dir: Working directory
            description: Human-readable description of the command (for logging)

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        try:
            logger.info(f"{description}: Running {' '.join(command)}")

            result = subprocess.run(
                command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout per command
            )

            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as e:
            error_msg = f"{description} timed out after 60 seconds"
            logger.error(error_msg)
            raise TerraformValidationError(error_msg)
        except Exception as e:
            error_msg = f"Failed to run {description}: {e}"
            logger.error(error_msg)
            raise TerraformValidationError(error_msg)

    def _parse_terraform_diagnostics(self, json_output: str) -> List[dict]:
        """
        Parse terraform validate -json output to extract diagnostics.

        Args:
            json_output: JSON output from terraform validate -json

        Returns:
            List of diagnostic objects with fields: severity, summary, detail, range, module_address
        """
        diagnostics_list = []
        try:
            if not json_output.strip():
                return diagnostics_list

            data = json.loads(json_output)
            if isinstance(data, dict) and "diagnostics" in data:
                raw_diagnostics = data.get("diagnostics", [])
                if isinstance(raw_diagnostics, list):
                    for diag in raw_diagnostics:
                        # Extract core diagnostic fields
                        parsed = {
                            "severity": diag.get("severity", "unknown"),  # error, warning
                            "summary": diag.get("summary", ""),
                            "detail": diag.get("detail", ""),
                            "range": diag.get("range", {}),  # {filename, start, end}
                            "module_address": diag.get("module_address", ""),
                        }
                        diagnostics_list.append(parsed)
            logger.debug(f"Parsed {len(diagnostics_list)} Terraform diagnostics")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse terraform validate JSON output: {e}")
        except Exception as e:
            logger.warning(f"Error extracting diagnostics: {e}")
        return diagnostics_list

    def validate(
        self,
        terraform_files: Dict[str, str],
        source_system: str = "unknown",
    ) -> Dict[str, any]:
        """
        Validate generated Terraform configuration.

        Args:
            terraform_files: Dict of {filename: content}
                Should contain 'locals.tf' and 'glue.tf' files
            source_system: Source system name (for logging)

        Returns:
            Dict with keys:
                - status: 'passed' | 'failed'
                - logs: All captured stdout from all commands
                - errors: Captured stderr if any command failed
                - failed_command: Which command failed (if status is 'failed')
                - terraform_validation_diagnostics: List of parsed diagnostics from terraform validate -json
        """
        logs: list[str] = []
        all_errors: list[str] = []
        failed_command: Optional[str] = None
        terraform_diagnostics: List[dict] = []

        try:
            # Step 1: Create temporary directory
            work_dir = self._create_temp_directory()
            logger.info(f"[{source_system}] Starting Terraform validation")
            logs.append(f"Terraform validation started for {source_system}\n")

            # Step 2: Write Terraform files
            self._write_terraform_files(work_dir, terraform_files)
            logs.append(f"Terraform files written to {work_dir}\n")

            # Step 3: Run terraform init -backend=false
            logger.info(f"[{source_system}] Running terraform init")
            init_stdout, init_stderr, init_rc = self._run_command(
                ["terraform", "init", "-backend=false"],
                work_dir,
                "terraform init"
            )
            logs.append(f"=== terraform init ===\n{init_stdout}\n")
            if init_stderr:
                all_errors.append(f"terraform init stderr:\n{init_stderr}\n")

            if init_rc != 0:
                failed_command = "terraform init"
                raise TerraformValidationError(
                    f"terraform init failed with exit code {init_rc}: {init_stderr}"
                )

            # Step 4: Run terraform fmt -check -recursive
            logger.info(f"[{source_system}] Running terraform fmt -check -recursive")
            fmt_stdout, fmt_stderr, fmt_rc = self._run_command(
                ["terraform", "fmt", "-check", "-recursive"],
                work_dir,
                "terraform fmt -check"
            )
            logs.append(f"=== terraform fmt -check ===\n{fmt_stdout}\n")
            if fmt_stderr:
                all_errors.append(f"terraform fmt stderr:\n{fmt_stderr}\n")

            if fmt_rc != 0:
                failed_command = "terraform fmt -check"
                raise TerraformValidationError(
                    f"terraform fmt check failed with exit code {fmt_rc}\n"
                    f"Formatting issues found:\n{fmt_stderr or fmt_stdout}"
                )

            # Step 5: Run terraform validate -json
            logger.info(f"[{source_system}] Running terraform validate -json")
            validate_stdout, validate_stderr, validate_rc = self._run_command(
                ["terraform", "validate", "-json"],
                work_dir,
                "terraform validate"
            )
            logs.append(f"=== terraform validate -json ===\n{validate_stdout}\n")
            if validate_stderr:
                all_errors.append(f"terraform validate stderr:\n{validate_stderr}\n")

            # Parse JSON diagnostics from terraform validate -json
            terraform_diagnostics = self._parse_terraform_diagnostics(validate_stdout)

            if validate_rc != 0:
                failed_command = "terraform validate"
                raise TerraformValidationError(
                    f"terraform validate failed with exit code {validate_rc}:\n{validate_stderr}"
                )

            # All validations passed
            logger.info(f"[{source_system}] ✅ All Terraform validations passed")
            logs.append(f"\n✅ All Terraform validations passed for {source_system}\n")

            return {
                "status": "passed",
                "logs": "".join(logs),
                "errors": "",
                "failed_command": None,
                "terraform_validation_diagnostics": terraform_diagnostics,
            }

        except TerraformValidationError as e:
            logger.error(f"[{source_system}] ❌ Terraform validation failed: {e}")
            logs.append(f"\n❌ Validation failed: {str(e)}\n")
            return {
                "status": "failed",
                "logs": "".join(logs),
                "errors": "\n".join(all_errors) if all_errors else str(e),
                "failed_command": failed_command,
                "terraform_validation_diagnostics": terraform_diagnostics,
            }
        finally:
            # Always cleanup temp directory
            self._cleanup_temp_directory()
