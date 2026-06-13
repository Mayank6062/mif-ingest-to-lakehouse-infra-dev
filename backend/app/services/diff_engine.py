"""
Diff Engine Service — Track and analyze changes.

This module extends the basic DiffEngine with:
- File change detection
- Conflict detection (placeholder)
- Change summaries
- User-facing diff formatting
"""

from typing import List, Optional, Dict, Tuple
from app.models.diff import DiffEngine, FileDiff, ChangeSet, DiffType, DiffStatistics
from app.models.state_v2 import DraftFile, GlueJobEntry


class DiffEngineService:
    """
    Service for computing and presenting diffs.
    
    Usage:
    ```python
    service = DiffEngineService()
    
    # Get diff summary
    summary = service.get_diff_summary(changeset)
    
    # Format for UI display
    ui_text = service.format_changeset_for_ui(changeset)
    ```
    """
    
    def __init__(self):
        """Initialize diff engine service."""
        pass
    
    @staticmethod
    def get_diff_summary(changeset: ChangeSet) -> str:
        """
        Get human-readable summary of changeset.
        
        Example:
            "3 files added, 2 modified, 0 deleted. 1 new Glue job."
        """
        parts = []
        
        # File summary
        if changeset['files_added'] > 0:
            parts.append(f"{changeset['files_added']} file(s) added")
        if changeset['files_modified'] > 0:
            parts.append(f"{changeset['files_modified']} file(s) modified")
        if changeset['files_deleted'] > 0:
            parts.append(f"{changeset['files_deleted']} file(s) deleted")
        
        # Job summary
        if changeset['jobs_added'] > 0:
            parts.append(f"{changeset['jobs_added']} job(s) added")
        if changeset['jobs_modified'] > 0:
            parts.append(f"{changeset['jobs_modified']} job(s) modified")
        if changeset['jobs_deleted'] > 0:
            parts.append(f"{changeset['jobs_deleted']} job(s) deleted")
        
        if not parts:
            return "No changes"
        
        return ", ".join(parts) + "."
    
    @staticmethod
    def format_file_diff_for_ui(file_diff: FileDiff) -> str:
        """Format single file diff for UI display."""
        path = file_diff['file_path']
        diff_type = file_diff['diff_type']
        
        if diff_type == DiffType.ADDED:
            return f"✅ New: {path} (+{file_diff.get('lines_added', 0)} lines)"
        elif diff_type == DiffType.MODIFIED:
            added = file_diff.get('lines_added', 0)
            removed = file_diff.get('lines_removed', 0)
            return f"🔄 Modified: {path} (+{added} -{removed} lines)"
        elif diff_type == DiffType.DELETED:
            return f"❌ Deleted: {path}"
        elif diff_type == DiffType.RENAMED:
            old_path = file_diff.get('old_path', '')
            new_path = file_diff.get('new_path', '')
            return f"🔗 Renamed: {old_path} → {new_path}"
        else:
            return f"  Unchanged: {path}"
    
    @staticmethod
    def format_changeset_for_ui(changeset: ChangeSet) -> str:
        """Format complete changeset for UI display."""
        lines = []
        lines.append("=== Changes ===\n")
        
        # File changes
        if changeset['file_diffs']:
            lines.append("**Files:**")
            for file_diff in changeset['file_diffs']:
                if file_diff['diff_type'] != DiffType.UNCHANGED:
                    lines.append(f"  {DiffEngineService.format_file_diff_for_ui(file_diff)}")
            lines.append("")
        
        # Job changes
        if changeset['job_diffs']:
            lines.append("**Glue Jobs:**")
            for job_diff in changeset['job_diffs']:
                job_id = job_diff['job_id']
                diff_type = job_diff['diff_type']
                if diff_type == DiffType.ADDED:
                    lines.append(f"  ✅ New: {job_id}")
                elif diff_type == DiffType.MODIFIED:
                    lines.append(f"  🔄 Modified: {job_id}")
                elif diff_type == DiffType.DELETED:
                    lines.append(f"  ❌ Deleted: {job_id}")
            lines.append("")
        
        # Stats
        lines.append("**Summary:**")
        stats = DiffEngine.compute_statistics(changeset)
        lines.append(f"  Files: {stats['files_changed']} changed")
        lines.append(f"  Lines: +{stats['lines_added']} -{stats['lines_removed']}")
        
        return "\n".join(lines)
    
    @staticmethod
    def get_changed_files(changeset: ChangeSet) -> List[str]:
        """Get list of all changed file paths."""
        return [
            diff['file_path'] 
            for diff in changeset['file_diffs']
            if diff['diff_type'] != DiffType.UNCHANGED
        ]
    
    @staticmethod
    def get_file_diff(changeset: ChangeSet, file_path: str) -> Optional[FileDiff]:
        """Get diff for specific file."""
        for diff in changeset['file_diffs']:
            if diff['file_path'] == file_path:
                return diff
        return None
    
    @staticmethod
    def has_conflicts(changeset: ChangeSet) -> bool:
        """
        Check if changeset has conflicts.
        
        (Placeholder for Phase 2 conflict resolution)
        
        Returns:
            True if conflicts detected
        """
        # TODO: Implement conflict detection
        return False
    
    @staticmethod
    def analyze_impact(changeset: ChangeSet) -> Dict[str, any]:
        """
        Analyze the impact of changes.
        
        Returns:
            Dictionary with impact analysis:
            - files_affected: count
            - jobs_affected: count
            - risk_level: low/medium/high
            - breaking_changes: list
        """
        risk_level = "low"
        breaking_changes = []
        
        # Detect risky changes
        for job_diff in changeset['job_diffs']:
            if job_diff['diff_type'] == DiffType.DELETED:
                breaking_changes.append(f"Deleted job: {job_diff['job_id']}")
                risk_level = "high"
        
        for file_diff in changeset['file_diffs']:
            if file_diff['diff_type'] == DiffType.DELETED:
                if 'terraform' in file_diff['file_path']:
                    breaking_changes.append(f"Deleted Terraform file: {file_diff['file_path']}")
                    risk_level = "high"
        
        if changeset['files_modified'] > 0:
            if risk_level == "low":
                risk_level = "medium"
        
        return {
            'files_affected': changeset['files_added'] + changeset['files_modified'] + changeset['files_deleted'],
            'jobs_affected': changeset['jobs_added'] + changeset['jobs_modified'] + changeset['jobs_deleted'],
            'risk_level': risk_level,
            'breaking_changes': breaking_changes,
            'total_changes': changeset['total_changes'],
        }
    
    @staticmethod
    def compare_terraform_syntax(old_content: str, new_content: str) -> Tuple[bool, Optional[str]]:
        """
        Check if Terraform syntax changed (for validation step).
        
        Args:
            old_content: previous Terraform code
            new_content: new Terraform code
        
        Returns:
            (syntax_valid, error_message)
            (True, None) if both valid
            (False, error_msg) if invalid
        """
        # TODO: Integrate with tfsec or terraform validate
        # For now, just check for obvious syntax errors
        
        if not new_content:
            return False, "Empty Terraform content"
        
        # Basic checks
        if new_content.count('{') != new_content.count('}'):
            return False, "Mismatched braces in Terraform"
        
        if new_content.count('[') != new_content.count(']'):
            return False, "Mismatched brackets in Terraform"
        
        if new_content.count('(') != new_content.count(')'):
            return False, "Mismatched parentheses in Terraform"
        
        return True, None
