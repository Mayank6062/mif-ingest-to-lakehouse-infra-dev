"""
Diff Engine — Track changes between snapshots.

This module provides:
- DiffType: enum of change types (add, modify, delete, rename)
- FileDiff: single file change
- ChangeSet: complete diff between two snapshots
- DiffEngine: compute and track diffs

Diffs are immutable, versioned, and stored in Snapshots.
"""

from typing import TypedDict, List, Optional, Literal
from enum import Enum
from datetime import datetime


class DiffType(str, Enum):
    """Change types tracked by diff engine."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    UNCHANGED = "unchanged"


class LineDiff(TypedDict, total=False):
    """Line-by-line diff for modified files."""
    line_number: int
    line_type: Literal["added", "removed", "context"]
    content: str
    context_before: Optional[str]
    context_after: Optional[str]


class FileDiff(TypedDict, total=False):
    """Change to a single file."""
    file_path: str
    diff_type: DiffType
    old_content: Optional[str]
    new_content: Optional[str]
    old_path: Optional[str]  # for renames
    new_path: Optional[str]
    size_before: int
    size_after: int
    lines_added: int
    lines_removed: int
    line_diffs: Optional[List[LineDiff]]  # detailed line-by-line changes


class GlueJobDiff(TypedDict, total=False):
    """Change to Glue job metadata."""
    job_id: str
    diff_type: DiffType
    old_value: dict
    new_value: dict


class ChangeSet(TypedDict, total=False):
    """Complete diff between two snapshots."""
    changeset_id: str
    from_snapshot_id: str
    to_snapshot_id: str
    timestamp: datetime
    
    # File changes
    file_diffs: List[FileDiff]
    files_added: int
    files_modified: int
    files_deleted: int
    files_renamed: int
    
    # Glue job changes
    job_diffs: List[GlueJobDiff]
    jobs_added: int
    jobs_modified: int
    jobs_deleted: int
    
    # Validation changes
    validation_diff: dict  # before/after validation reports
    
    # Summary
    total_changes: int
    summary: str


class DiffStatistics(TypedDict, total=False):
    """Statistics about changes."""
    files_changed: int
    lines_added: int
    lines_removed: int
    total_lines_changed: int
    insertions: int
    deletions: int
    size_delta: int  # bytes added/removed


class ConflictMarker(TypedDict, total=False):
    """Detected conflict in files (for future conflict resolution)."""
    file_path: str
    line_numbers: List[int]
    our_content: str
    their_content: str
    suggested_resolution: Optional[str]


class MergeConflict(TypedDict, total=False):
    """Merge conflict between snapshots."""
    conflict_id: str
    file_path: str
    conflict_type: Literal["content", "deletion", "rename"]
    markers: List[ConflictMarker]
    resolvable: bool
    suggested_resolution: Optional[str]


class DiffEngine:
    """Compute and track diffs between snapshots."""
    
    def __init__(self):
        """Initialize diff engine."""
        pass
    
    @staticmethod
    def compute_file_diff(old_content: Optional[str], new_content: Optional[str], file_path: str) -> FileDiff:
        """
        Compute diff for a single file.
        
        Returns:
            FileDiff with change type, line counts, and detailed diff
        """
        if old_content is None and new_content is not None:
            diff_type = DiffType.ADDED
            size_before = 0
            size_after = len(new_content)
            lines_added = new_content.count('\n') + 1
            lines_removed = 0
        elif old_content is not None and new_content is None:
            diff_type = DiffType.DELETED
            size_before = len(old_content)
            size_after = 0
            lines_added = 0
            lines_removed = old_content.count('\n') + 1
        elif old_content == new_content:
            diff_type = DiffType.UNCHANGED
            size_before = len(old_content) if old_content else 0
            size_after = len(new_content) if new_content else 0
            lines_added = 0
            lines_removed = 0
        else:
            diff_type = DiffType.MODIFIED
            size_before = len(old_content) if old_content else 0
            size_after = len(new_content) if new_content else 0
            # Simplified line counting
            old_lines = (old_content or "").split('\n')
            new_lines = (new_content or "").split('\n')
            lines_added = len(new_lines)
            lines_removed = len(old_lines)
        
        return FileDiff(
            file_path=file_path,
            diff_type=diff_type,
            old_content=old_content,
            new_content=new_content,
            size_before=size_before,
            size_after=size_after,
            lines_added=lines_added,
            lines_removed=lines_removed,
        )
    
    @staticmethod
    def compute_changeset(
        changeset_id: str,
        from_snapshot_id: str,
        to_snapshot_id: str,
        old_files: List[dict],
        new_files: List[dict],
        old_jobs: Optional[List[dict]] = None,
        new_jobs: Optional[List[dict]] = None,
    ) -> ChangeSet:
        """
        Compute complete diff between two snapshots.
        
        Args:
            changeset_id: unique ID for this changeset
            from_snapshot_id: starting snapshot
            to_snapshot_id: ending snapshot
            old_files: files from old snapshot
            new_files: files from new snapshot
            old_jobs: glue jobs from old snapshot
            new_jobs: glue jobs from new snapshot
        
        Returns:
            ChangeSet with all file and job diffs
        """
        # Build path → content maps
        old_map = {f['path']: f['content'] for f in old_files}
        new_map = {f['path']: f.get('content') for f in new_files}
        
        file_diffs: List[FileDiff] = []
        files_added = 0
        files_modified = 0
        files_deleted = 0
        files_renamed = 0
        
        # Find added and modified files
        for path, new_content in new_map.items():
            if path not in old_map:
                files_added += 1
            else:
                if old_map[path] != new_content:
                    files_modified += 1
            
            file_diff = DiffEngine.compute_file_diff(
                old_map.get(path),
                new_content,
                path
            )
            if file_diff['diff_type'] != DiffType.UNCHANGED:
                file_diffs.append(file_diff)
        
        # Find deleted files
        for path in old_map:
            if path not in new_map:
                files_deleted += 1
                file_diff = DiffEngine.compute_file_diff(old_map[path], None, path)
                file_diffs.append(file_diff)
        
        # Compute job diffs
        job_diffs: List[GlueJobDiff] = []
        jobs_added = 0
        jobs_modified = 0
        jobs_deleted = 0
        
        if old_jobs is None:
            old_jobs = []
        if new_jobs is None:
            new_jobs = []
        
        old_job_map = {job['job_id']: job for job in old_jobs}
        new_job_map = {job['job_id']: job for job in new_jobs}
        
        for job_id, new_job in new_job_map.items():
            if job_id not in old_job_map:
                jobs_added += 1
                job_diffs.append(GlueJobDiff(
                    job_id=job_id,
                    diff_type=DiffType.ADDED,
                    new_value=new_job,
                ))
            elif old_job_map[job_id] != new_job:
                jobs_modified += 1
                job_diffs.append(GlueJobDiff(
                    job_id=job_id,
                    diff_type=DiffType.MODIFIED,
                    old_value=old_job_map[job_id],
                    new_value=new_job,
                ))
        
        for job_id in old_job_map:
            if job_id not in new_job_map:
                jobs_deleted += 1
                job_diffs.append(GlueJobDiff(
                    job_id=job_id,
                    diff_type=DiffType.DELETED,
                    old_value=old_job_map[job_id],
                ))
        
        total_changes = (
            files_added + files_modified + files_deleted +
            jobs_added + jobs_modified + jobs_deleted
        )
        
        summary = (
            f"{files_added}+ {files_modified}~ {files_deleted}- files, "
            f"{jobs_added}+ {jobs_modified}~ {jobs_deleted}- jobs"
        )
        
        return ChangeSet(
            changeset_id=changeset_id,
            from_snapshot_id=from_snapshot_id,
            to_snapshot_id=to_snapshot_id,
            timestamp=datetime.now(),
            file_diffs=file_diffs,
            files_added=files_added,
            files_modified=files_modified,
            files_deleted=files_deleted,
            files_renamed=files_renamed,
            job_diffs=job_diffs,
            jobs_added=jobs_added,
            jobs_modified=jobs_modified,
            jobs_deleted=jobs_deleted,
            total_changes=total_changes,
            summary=summary,
        )
    
    @staticmethod
    def detect_conflicts(
        changeset: ChangeSet,
        base_changeset: Optional[ChangeSet] = None,
    ) -> List[MergeConflict]:
        """
        Detect conflicts in a changeset.
        
        (Placeholder for conflict resolution in Phase 2 BLOCKER 2)
        
        Returns:
            List of detected conflicts
        """
        conflicts: List[MergeConflict] = []
        
        # TODO: Implement conflict detection
        # - Multiple edits to same file
        # - Job key collisions
        # - Source system path conflicts
        
        return conflicts
    
    @staticmethod
    def compute_statistics(changeset: ChangeSet) -> DiffStatistics:
        """Compute aggregate statistics from changeset."""
        insertions = 0
        deletions = 0
        
        for file_diff in changeset['file_diffs']:
            insertions += file_diff.get('lines_added', 0)
            deletions += file_diff.get('lines_removed', 0)
        
        return DiffStatistics(
            files_changed=changeset['files_added'] + changeset['files_modified'] + changeset['files_deleted'],
            lines_added=insertions,
            lines_removed=deletions,
            total_lines_changed=insertions + deletions,
            insertions=insertions,
            deletions=deletions,
            size_delta=sum(f.get('size_after', 0) - f.get('size_before', 0) for f in changeset['file_diffs']),
        )
