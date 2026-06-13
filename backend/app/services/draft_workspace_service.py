"""
Draft Workspace Service — CRUD and lifecycle management.

This module provides:
- DraftWorkspaceService: high-level API for draft operations
- File management (add, edit, delete)
- Glue job tracking
- Status transitions
- Validation report management
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.state_v2 import (
    DraftWorkspace,
    DraftWorkspaceStatus,
    DraftFile,
    GlueJobEntry,
    ValidationReport,
    create_draft_workspace,
)
from app.services.snapshot_engine import SnapshotEngine, SnapshotManager
from app.models.diff import DiffEngine


class DraftWorkspaceService:
    """
    Manage draft workspaces.
    
    Usage:
    ```python
    service = DraftWorkspaceService()
    
    # Create new draft
    draft = service.create_draft(session_id)
    
    # Add a file
    service.add_file(draft, "saptcc/locals.tf", content)
    
    # Create a Glue job entry
    service.add_glue_job(draft, "saptcc", "multi-1", topic, environment)
    
    # Run validation
    service.set_validation_status(draft, "pending")
    
    # Validate and lock
    service.validate_and_lock(draft)
    
    # Discard changes
    service.discard_last_change(draft)
    ```
    """
    
    def __init__(self):
        """Initialize draft workspace service."""
        self.snapshot_engine = SnapshotEngine()
        self.snapshot_manager = SnapshotManager(self.snapshot_engine)
        
        # In-memory storage: draft_id → DraftWorkspace
        self._drafts: Dict[str, DraftWorkspace] = {}
    
    def create_draft(
        self,
        session_id: str,
    ) -> DraftWorkspace:
        """
        Create a new draft workspace.
        
        Args:
            session_id: which session this draft belongs to
        
        Returns:
            New DraftWorkspace
        """
        draft_id = str(uuid.uuid4())
        draft = create_draft_workspace(draft_id, session_id)
        
        # Store draft
        self._drafts[draft_id] = draft
        
        # Create initial snapshot
        self.snapshot_manager.create_auto_snapshot(
            draft_id=draft_id,
            operation="create_draft",
            user_action=f"Created draft workspace",
            draft_workspace=draft,
        )
        
        return draft
    
    def get_draft(self, draft_id: str) -> Optional[DraftWorkspace]:
        """Retrieve draft by ID."""
        draft = self._drafts.get(draft_id)
        if not draft:
            return None
        # Return a shallow copy for external callers and serialize status
        s = draft.get('status')
        status_val = s.name if isinstance(s, DraftWorkspaceStatus) else str(s)
        copy = dict(draft)
        copy['status'] = status_val
        return copy
    
    def add_file(
        self,
        draft: DraftWorkspace,
        file_path: str,
        content: str,
        file_type: str = "terraform",
        editable: bool = True,
    ) -> DraftFile:
        """
        Add or update a file in draft.
        
        Args:
            draft: target draft workspace
            file_path: path relative to repo root (e.g., "saptcc/locals.tf")
            content: file content
            file_type: terraform | yaml | json | python | other
            editable: whether user can edit this file
        
        Returns:
            Created/updated DraftFile

        Raises:
            ValueError if draft is frozen (PR_CREATING)
        """
        # STEP 2.3: Draft Freeze Check
        if self.is_frozen(draft):
            raise ValueError("Cannot edit draft while PR creation is in progress")
        
        # Check if file exists
        existing_file = None
        for f in draft['files']:
            if f['path'] == file_path:
                existing_file = f
                break
        
        if existing_file:
            # Update existing
            existing_file['content'] = content
            existing_file['mtime'] = datetime.now()
        else:
            # Create new
            file_id = str(uuid.uuid4())
            draft_file: DraftFile = {
                'file_id': file_id,
                'draft_id': draft['draft_id'],
                'path': file_path,
                'content': content,
                'file_type': file_type,
                'mtime': datetime.now(),
                'editable': editable,
                'locked_by': None,
                'locked_at': None,
            }
            draft['files'].append(draft_file)
            existing_file = draft_file
        
        # Auto-snapshot
        self.snapshot_manager.create_auto_snapshot(
            draft_id=draft['draft_id'],
            operation="add_file",
            user_action=f"Added/edited file: {file_path}",
            draft_workspace=draft,
        )
        
        draft['updated_at'] = datetime.now()
        draft['status'] = DraftWorkspaceStatus.OPEN
        
        return existing_file
    
    def remove_file(self, draft: DraftWorkspace, file_path: str) -> bool:
        """
        Remove a file from draft.
        
        Returns:
            True if removed, False if not found
        """
        original_len = len(draft['files'])
        draft['files'] = [f for f in draft['files'] if f['path'] != file_path]
        
        if len(draft['files']) < original_len:
            # Auto-snapshot
            self.snapshot_manager.create_auto_snapshot(
                draft_id=draft['draft_id'],
                operation="remove_file",
                user_action=f"Removed file: {file_path}",
                draft_workspace=draft,
            )
            draft['updated_at'] = datetime.now()
            return True
        
        return False
    
    def get_file(self, draft: DraftWorkspace, file_path: str) -> Optional[DraftFile]:
        """Get a file from draft by path."""
        for f in draft['files']:
            if f['path'] == file_path:
                return f
        return None
    
    def add_glue_job(
        self,
        draft: DraftWorkspace,
        source_system: str,
        schema_grain: str,
        topic: str,
        environment: str,
        job_key: Optional[str] = None,
    ) -> GlueJobEntry:
        """
        Add a Glue job entry to draft.
        
        Args:
            draft: target draft workspace
            source_system: (e.g., "saptcc")
            schema_grain: (e.g., "multi-1")
            topic: Kafka topic
            environment: dev | snd | prod
            job_key: optional, auto-generated if not provided

        Raises:
            ValueError if draft is frozen (PR_CREATING)
        
        Returns:
            Created GlueJobEntry
        """
        # STEP 2.3: Draft Freeze Check
        if self.is_frozen(draft):
            raise ValueError("Cannot create Glue job while PR creation is in progress")
        
        job_id = str(uuid.uuid4())
        
        if not job_key:
            job_key = f"kafka-to-iceberg-batch-{source_system}-{schema_grain}"
        
        order = len(draft['glue_jobs']) + 1
        
        job_entry: GlueJobEntry = {
            'job_id': job_id,
            'job_key': job_key,
            'source_system': source_system,
            'schema_grain': schema_grain,
            'topic': topic,
            'environment': environment,
            'created_at': datetime.now(),
            'order_in_draft': order,
        }
        
        draft['glue_jobs'].append(job_entry)
        
        # Auto-snapshot
        self.snapshot_manager.create_auto_snapshot(
            draft_id=draft['draft_id'],
            operation="add_glue_job",
            user_action=f"Created Glue job: {job_key}",
            draft_workspace=draft,
        )
        
        draft['updated_at'] = datetime.now()
        draft['status'] = DraftWorkspaceStatus.OPEN
        
        return job_entry
    
    def set_validation_status(
        self,
        draft: DraftWorkspace,
        status: str,
        report: Optional[ValidationReport] = None,
    ) -> None:
        """
        Update validation status and optionally add/update report.
        
        Args:
            draft: target draft
            status: pending | running | passed | failed
            report: ValidationReport to add
        """
        if report:
            # Check if report already exists
            existing_idx = None
            for i, r in enumerate(draft['validation_reports']):
                if r.get('report_id') == report.get('report_id'):
                    existing_idx = i
                    break
            
            if existing_idx is not None:
                draft['validation_reports'][existing_idx] = report
            else:
                draft['validation_reports'].append(report)
            
            draft['last_validation_report_id'] = report['report_id']
        
        # Auto-snapshot if status changed
        self.snapshot_manager.create_auto_snapshot(
            draft_id=draft['draft_id'],
            operation="validation_status_changed",
            user_action=f"Validation status: {status}",
            draft_workspace=draft,
        )
        
        draft['updated_at'] = datetime.now()
    
    def validate_and_lock(self, draft: DraftWorkspace) -> bool:
        """
        Mark draft as validated and ready for PR.
        
        Requirements for validation:
        - At least one Glue job created
        - All files present
        - No validation failures
        
        Returns:
            True if validation passed, False if failed
        """
        # Check preconditions
        if not draft['glue_jobs']:
            return False
        
        if not draft['files']:
            return False
        
        # Check latest validation report
        if draft['last_validation_report_id']:
            report = next(
                (r for r in draft['validation_reports'] 
                 if r['report_id'] == draft['last_validation_report_id']),
                None
            )
            if report and report['status'] == 'failed':
                return False
        
        # Transition status
        draft['status'] = DraftWorkspaceStatus.VALIDATED
        draft['updated_at'] = datetime.now()
        
        # Auto-snapshot
        self.snapshot_manager.create_auto_snapshot(
            draft_id=draft['draft_id'],
            operation="validate_and_lock",
            user_action="Draft validated and ready for PR",
            draft_workspace=draft,
        )
        
        return True
    
    def discard_last_change(self, draft: DraftWorkspace) -> bool:
        """
        Undo the last operation (visible as "Discard Last Change" to user).
        
        Returns:
            True if undo succeeded, False if nothing to undo

        Raises:
            ValueError if draft is frozen (PR_CREATING)
        """
        # STEP 2.3: Draft Freeze Check
        if self.is_frozen(draft):
            raise ValueError("Cannot discard changes while PR creation is in progress")
        
        return self.snapshot_manager.undo_last_operation(draft)
    
    def mark_merged(self, draft: DraftWorkspace) -> None:
        """Mark draft as merged (after PR is merged)."""
        draft['status'] = DraftWorkspaceStatus.MERGED
        draft['updated_at'] = datetime.now()
    
    def mark_abandoned(self, draft: DraftWorkspace) -> None:
        """Mark draft as abandoned (user discarded it)."""
        draft['status'] = DraftWorkspaceStatus.ABANDONED
        draft['updated_at'] = datetime.now()
        
        # Clean up snapshots
        self.snapshot_engine.cleanup_draft(draft['draft_id'])
    
    def get_summary(self, draft: DraftWorkspace) -> Dict[str, Any]:
        """Get high-level summary of draft."""
        s = draft.get('status')
        status_val = s.name if isinstance(s, DraftWorkspaceStatus) else str(s)
        return {
            'draft_id': draft['draft_id'],
            'session_id': draft['session_id'],
            'status': status_val,
            'files_count': len(draft['files']),
            'glue_jobs_count': len(draft['glue_jobs']),
            'validation_reports_count': len(draft['validation_reports']),
            'snapshots_count': len(draft['snapshot_refs']),
            'created_at': draft['created_at'],
            'updated_at': draft['updated_at'],
            'glue_jobs': [
                {
                    'job_key': job['job_key'],
                    'source_system': job['source_system'],
                    'schema_grain': job['schema_grain'],
                    'created_at': job['created_at'],
                }
                for job in draft['glue_jobs']
            ],
        }

    def collect_final_files(self, draft_id: str) -> List[Dict[str, str]]:
        """
        STEP 2.3: Collect all final files from draft as the source of truth for PR.

        This method is the ONLY authoritative source for files that will be committed
        to GitHub. It returns a list of { path, content, mode } dicts ready to be
        passed to GitHubService.create_single_commit_and_pr().

        Args:
            draft_id: ID of the draft to collect files from

        Returns:
            List[{ path: str, content: str, mode: str }]
            - path: file path relative to repo root (e.g., "saptcc/locals.tf")
            - content: full file content (string)
            - mode: file mode (default "100644" for files)

        Raises:
            ValueError if draft not found

        Usage:
            ```python
            service = DraftWorkspaceService()
            files = service.collect_final_files("dft_xxxxx")
            # files = [
            #     { "path": "saptcc/locals.tf", "content": "...", "mode": "100644" },
            #     { "path": "saptcc/glue.tf", "content": "...", "mode": "100644" }
            # ]
            ```
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        final_files = []
        for file_obj in draft.get('files', []):
            final_files.append({
                'path': file_obj['path'],
                'content': file_obj['content'],
                'mode': '100644',  # Standard file mode
            })

        return final_files

    def update_draft_meta(
        self,
        draft_id: str,
        metadata: Dict[str, str],
    ) -> DraftWorkspace:
        """
        Update user-editable metadata for draft (branch name, commit message, PR title/body).

        Args:
            draft_id: ID of the draft
            metadata: Dict with keys:
                - branch_name: user-editable branch name
                - user_commit_message: user-editable commit message
                - user_pr_title: user-editable PR title
                - user_pr_description: user-editable PR description

        Returns:
            Updated DraftWorkspace
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        # Update metadata fields
        for key in ['branch_name', 'user_commit_message', 'user_pr_title', 'user_pr_description']:
            if key in metadata:
                draft[key] = metadata[key]

        draft['updated_at'] = datetime.now()
        return draft

    def set_draft_status(self, draft_id: str, status: str) -> DraftWorkspace:
        """
        Atomically set draft status (OPEN, REVIEW, PR_CREATING, PR_CREATED, ABANDONED).

        STEP 2.3: When transitioning to PR_CREATING, the draft is FROZEN and all
        mutation operations (add_file, add_glue_job, discard_last_change) will raise
        ValueError until the PR is created.

        Args:
            draft_id: ID of the draft
            status: new status (OPEN | REVIEW | PR_CREATING | PR_CREATED | ABANDONED)

        Returns:
            Updated DraftWorkspace
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        # Normalize status: if it matches a DraftWorkspaceStatus member name, store
        # the Enum member for better compatibility with existing tests/code.
        if isinstance(status, str) and status in DraftWorkspaceStatus.__members__:
            draft['status'] = DraftWorkspaceStatus[status]
        else:
            # Store as-is (typically strings like 'PR_CREATING' / 'PR_CREATED')
            draft['status'] = status
        draft['updated_at'] = datetime.now()
        
        # Auto-snapshot on status change
        self.snapshot_manager.create_auto_snapshot(
            draft_id=draft_id,
            operation="set_draft_status",
            user_action=f"Draft status changed to {status}",
            draft_workspace=draft,
        )
        
        return draft

    def is_frozen(self, draft: DraftWorkspace) -> bool:
        """
        Check if draft is frozen (status = PR_CREATING).
        
        When frozen, mutation operations raise ValueError:
        - add_file
        - add_glue_job
        - discard_last_change
        
        Returns:
            True if draft is frozen, False otherwise
        """
        # Normalize status name for comparison. Draft status may be stored as
        # an Enum member or as a string (legacy PR lifecycle names).
        s = draft.get('status')
        if isinstance(s, DraftWorkspaceStatus):
            name = s.name
        else:
            name = str(s)
        return name == 'PR_CREATING'

    def check_duplicate_pr_protection(self, draft_id: str) -> None:
        """
        STEP 2.3: Duplicate PR Protection check.
        
        Prevents concurrent PR creation requests for the same draft.
        If a draft is already PR_CREATING, raises ValueError to block
        second attempt.
        
        Args:
            draft_id: ID of the draft
        
        Raises:
            ValueError if draft is already in PR_CREATING status
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")
        # Compare normalized name
        s = draft.get('status')
        if isinstance(s, DraftWorkspaceStatus):
            name = s.name
        else:
            name = str(s)
        
        if name == 'PR_CREATING':
            raise ValueError(
                f"Draft {draft_id} is already creating a PR. "
                "Please wait for it to complete."
            )

    def mark_draft_pr_creating(self, draft_id: str) -> DraftWorkspace:
        """
        STEP 2.3: Mark draft as PR_CREATING (atomic transition).
        
        This enforces that only one PR creation request can proceed at a time.
        The draft is frozen until PR is created.
        
        Args:
            draft_id: ID of the draft
        
        Returns:
            Updated DraftWorkspace (with status = PR_CREATING)
        
        Raises:
            ValueError if draft already PR_CREATING (duplicate protection)
        """
        self.check_duplicate_pr_protection(draft_id)
        return self.set_draft_status(draft_id, 'PR_CREATING')

    def mark_draft_pr_created(
        self,
        draft_id: str,
        pr_metadata: Dict[str, any],
    ) -> DraftWorkspace:
        """
        Mark draft as PR_CREATED and store PR metadata.

        Args:
            draft_id: ID of the draft
            pr_metadata: Dict with keys:
                - pr_url: GitHub PR URL
                - pr_number: GitHub PR number
                - commit_sha: SHA of the commit

        Returns:
            Updated DraftWorkspace
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        draft['status'] = 'PR_CREATED'
        draft['pr_url'] = pr_metadata.get('pr_url')
        draft['pr_number'] = pr_metadata.get('pr_number')
        draft['commit_sha'] = pr_metadata.get('commit_sha')
        draft['updated_at'] = datetime.now()

        return draft

    def preview_diff(self, draft_id: str) -> Dict[str, any]:
        """
        Compute diff/patch for all files in draft without committing.

        Returns summary of changes for preview screen.

        Args:
            draft_id: ID of the draft

        Returns:
            { files_count, total_size, file_list: [{ path, size }] }
        """
        draft = self._drafts.get(draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        total_size = 0
        file_list = []

        for file_obj in draft.get('files', []):
            size = len(file_obj['content'].encode('utf-8'))
            total_size += size
            file_list.append({
                'path': file_obj['path'],
                'size': size,
                'type': file_obj.get('file_type', 'terraform'),
            })

        return {
            'draft_id': draft_id,
            'files_count': len(file_list),
            'total_size': total_size,
            'file_list': file_list,
        }
