"""
State Model V2 — Complete session and draft workspace entity definitions.

This module defines the authoritative data structures for:
- Session: User session metadata, message history, draft workspace references
- DraftWorkspace: Mutable working area for Glue job creation + modifications
- DraftFile: Individual Terraform/YAML files in the draft
- ValidationReport: Results from 4-validator pipeline
- Snapshot: Immutable point-in-time capture of draft state

All entities use TypedDict for type safety and JSON serialization.
"""

from typing import TypedDict, Optional, List, Literal, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """Session lifecycle states."""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    PR_CREATED = "pr_created"
    ARCHIVED = "archived"


class DraftWorkspaceStatus(str, Enum):
    """Draft workspace lifecycle states."""
    OPEN = "open"
    VALIDATED = "validated"
    READY_FOR_PR = "ready_for_pr"
    MERGED = "merged"
    ABANDONED = "abandoned"


# ─── Message & Action Cards ────────────────────────────────────────────────

class ActionCard(TypedDict, total=False):
    """User-facing action card (approve, confirm, select option)."""
    card_id: str
    card_type: Literal["approval", "confirmation", "selection", "form"]
    message: str
    options: List[str]  # for selection cards
    applied_at: Optional[datetime]  # None if not yet applied


class Message(TypedDict, total=False):
    """Chat message — immutable once created."""
    message_id: str
    timestamp: datetime
    role: Literal["assistant", "user", "system"]
    content: str
    actions: List[ActionCard]  # attached interactive elements
    step_name: Optional[str]  # which workflow step generated this


# ─── Validation ────────────────────────────────────────────────────────────

class ValidatorFinding(TypedDict, total=False):
    """One finding from a validator (Kafka, Schema, Terraform, tfsec)."""
    validator: str  # "kafka" | "schema" | "terraform" | "tfsec"
    level: Literal["error", "warning", "info"]
    blocking: bool  # True = halt workflow
    message: str
    details: Optional[dict]  # validator-specific details


class ValidationReport(TypedDict, total=False):
    """Complete validation report for a draft workspace."""
    report_id: str
    draft_id: str
    timestamp: datetime
    status: Literal["pending", "running", "passed", "failed"]
    findings: List[ValidatorFinding]
    summary: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# ─── Files ────────────────────────────────────────────────────────────────

class DraftFile(TypedDict, total=False):
    """One file in draft workspace (Terraform, YAML, script, etc.)."""
    file_id: str
    draft_id: str
    path: str  # relative path in repo (e.g., "saptcc/locals.tf")
    content: str  # full file content
    file_type: Literal["terraform", "yaml", "json", "python", "other"]
    mtime: datetime  # last modified time
    editable: bool  # True = user can edit in Draft Workspace UI
    locked_by: Optional[str]  # session_id if locked (optimistic locking)
    locked_at: Optional[datetime]


# ─── Glue Job Metadata (stored in DraftWorkspace) ────────────────────────

class GlueJobEntry(TypedDict, total=False):
    """Metadata for one Glue job in draft."""
    job_id: str
    job_key: str  # kafka-to-iceberg-batch-saptcc-multi-1
    source_system: str
    schema_grain: str
    topic: str
    environment: str
    created_at: datetime
    order_in_draft: int  # 1, 2, 3... for multiple jobs in same draft


# ─── Snapshots ─────────────────────────────────────────────────────────────

class SnapshotMetadata(TypedDict, total=False):
    """Metadata for a snapshot (not the full state)."""
    snapshot_id: str
    draft_id: str
    parent_snapshot_id: Optional[str]
    timestamp: datetime
    operation: str  # "create_job", "edit_file", "run_validation", "confirm"
    user_action: str  # describes what triggered this snapshot


class Snapshot(TypedDict, total=False):
    """Complete immutable snapshot of draft workspace state."""
    snapshot_id: str
    draft_id: str
    parent_snapshot_id: Optional[str]
    timestamp: datetime
    operation: str
    user_action: str
    # Full draft state at this point
    files: List[DraftFile]
    glue_jobs: List[GlueJobEntry]
    validation_reports: List[ValidationReport]
    metadata: dict  # any additional context


# ─── Draft Workspace ───────────────────────────────────────────────────────

class DraftWorkspace(TypedDict, total=False):
    """Mutable working area for one or more Glue job creations."""
    draft_id: str
    session_id: str
    status: DraftWorkspaceStatus
    
    # Core content
    files: List[DraftFile]  # all files in this draft
    glue_jobs: List[GlueJobEntry]  # jobs created in this draft
    
    # Validation & review
    validation_reports: List[ValidationReport]  # validation runs
    last_validation_report_id: Optional[str]  # most recent validation
    
    # Snapshots & undo
    snapshot_refs: List[str]  # list of snapshot IDs (for undo/redo)
    current_snapshot_index: int  # index into snapshot_refs
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    last_change_timestamp: Optional[datetime]  # for "discard last change"
    
    # Locking (optimistic)
    locked_by: Optional[str]  # session_id if locked
    locked_at: Optional[datetime]


# ─── Session (Root Entity) ─────────────────────────────────────────────────

class Session(TypedDict, total=False):
    """User session — root entity for all state in a user's workspace."""
    session_id: str
    user_email: str
    github_username: Optional[str]
    
    # Current draft workspace
    current_draft_id: Optional[str]  # FK to DraftWorkspace
    
    # Message history (accumulated, never overwritten)
    message_history: List[Message]
    
    # Session lifecycle
    status: SessionStatus
    environment: Literal["dev", "snd", "prod"]  # selected environment
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    oauth_token: Optional[str]  # GitHub OAuth token (encrypted in DB)
    
    # Session settings
    repository_url: str  # full GitHub repo URL
    base_branch: str  # usually "main"


# ─── NavigatorState (Repository Index) ──────────────────────────────────

class RelatedIndex(TypedDict, total=False):
    """Cached repository navigation index."""
    source_systems: List[str]  # list of {source_system}/ folders
    topics_files: dict  # {source_system: path_to_topics_*.tf}
    locals_files: dict  # {source_system: path_to_locals.tf}
    glue_files: dict  # {source_system: path_to_glue.tf}
    cache_timestamp: datetime
    repo_index_version: str  # to detect stale cache


class NavigatorState(TypedDict, total=False):
    """Repository navigation state (for context-aware suggestions)."""
    session_id: str
    environment: str
    repository_root: str
    source_system: Optional[str]
    schema_grain: Optional[str]
    related_index: RelatedIndex
    last_index_update: datetime


# ─── Message Payload Helpers ───────────────────────────────────────────────

class MessagePayload(TypedDict, total=False):
    """Standard message payload for frontend consumption."""
    message_id: str
    timestamp: datetime
    role: Literal["assistant", "user", "system"]
    content: str
    actions: List[ActionCard]
    step: Optional[str]
    step_number: Optional[int]
    total_steps: Optional[int]


# ─── Status Tracking ─────────────────────────────────────────────────────

class WorkflowProgress(TypedDict, total=False):
    """Real-time workflow progress."""
    session_id: str
    current_step: str
    step_number: int
    total_steps: int
    pending_user_input: bool
    error: Optional[str]
    retryable: bool


# ─── Helper Functions ──────────────────────────────────────────────────────

def create_session(
    session_id: str,
    user_email: str,
    environment: str = "dev",
    repository_url: str = "",
    base_branch: str = "main"
) -> Session:
    """Create a new session."""
    now = datetime.now()
    return Session(
        session_id=session_id,
        user_email=user_email,
        github_username=None,
        current_draft_id=None,
        message_history=[],
        status=SessionStatus.ACTIVE,
        environment=environment,
        created_at=now,
        updated_at=now,
        last_activity_at=now,
        oauth_token=None,
        repository_url=repository_url,
        base_branch=base_branch,
    )


def create_draft_workspace(
    draft_id: str,
    session_id: str
) -> DraftWorkspace:
    """Create a new draft workspace."""
    now = datetime.now()
    return DraftWorkspace(
        draft_id=draft_id,
        session_id=session_id,
        status=DraftWorkspaceStatus.OPEN,
        files=[],
        glue_jobs=[],
        validation_reports=[],
        last_validation_report_id=None,
        snapshot_refs=[],
        current_snapshot_index=0,
        created_at=now,
        updated_at=now,
        last_change_timestamp=None,
        locked_by=None,
        locked_at=None,
    )


def create_message(
    message_id: str,
    role: Literal["assistant", "user", "system"],
    content: str,
    step_name: Optional[str] = None,
    actions: Optional[List[ActionCard]] = None
) -> Message:
    """Create a chat message."""
    return Message(
        message_id=message_id,
        timestamp=datetime.now(),
        role=role,
        content=content,
        actions=actions or [],
        step_name=step_name,
    )


def create_validation_report(
    report_id: str,
    draft_id: str
) -> ValidationReport:
    """Create a new validation report."""
    return ValidationReport(
        report_id=report_id,
        draft_id=draft_id,
        timestamp=datetime.now(),
        status="pending",
        findings=[],
        summary="",
        started_at=None,
        completed_at=None,
    )


def create_snapshot(
    snapshot_id: str,
    draft_id: str,
    operation: str,
    user_action: str,
    files: List[DraftFile],
    glue_jobs: List[GlueJobEntry],
    validation_reports: List[ValidationReport],
    parent_snapshot_id: Optional[str] = None,
) -> Snapshot:
    """Create a snapshot of current draft state."""
    return Snapshot(
        snapshot_id=snapshot_id,
        draft_id=draft_id,
        parent_snapshot_id=parent_snapshot_id,
        timestamp=datetime.now(),
        operation=operation,
        user_action=user_action,
        files=files,
        glue_jobs=glue_jobs,
        validation_reports=validation_reports,
        metadata={},
    )
