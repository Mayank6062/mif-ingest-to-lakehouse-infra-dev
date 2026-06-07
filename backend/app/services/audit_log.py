"""
Audit logging service — structured, append-only JSONL audit trail.

Writes one JSON record per event to the "audit" logger, which is configured
in main.py to emit to backend/logs/audit.jsonl via TimedRotatingFileHandler.

Design guarantees:
  - log_event() NEVER raises — all exceptions are swallowed internally.
  - Forbidden fields (terraform_hcl, locals_tf_full, glue_tf_content,
    github_token, azure_openai_api_key, session_token, Authorization)
    are never referenced — schema is built from explicit field extractions only.
  - Every field is extracted by name — state is never spread or serialised whole.
  - correlation_id always mirrors session_id (forward-compat for distributed tracing).
"""

import json
import logging
from datetime import datetime, timezone

_audit_logger = logging.getLogger("audit")


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 with milliseconds: 2026-06-06T14:23:01.456Z"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def log_event(
    event: str,
    actor: str,
    state: dict,
    *,
    pr_number: int | None = None,
    pr_url: str | None = None,
    error: str | None = None,
) -> None:
    """
    Emit one structured audit record to the "audit" logger.

    Args:
        event:     Event name — one of: session_created, approval_received,
                   approval_rejected, pr_creation_started, pr_creation_succeeded,
                   pr_creation_failed.
        actor:     "user" for approval events; "system" for session/PR events.
        state:     GlueJobState dict — fields extracted by explicit name only.
                   Forbidden content-bearing fields are never accessed.
        pr_number: GitHub PR number (pr_creation_succeeded only).
        pr_url:    GitHub PR URL (pr_creation_succeeded only).
        error:     Exception message string (pr_creation_failed only).

    Never raises — all exceptions are silently absorbed to protect workflow execution.
    Workflow must always continue regardless of logging outcome.
    """
    try:
        session_id = state.get("session_id")
        record = {
            "event_version": 1,
            "event":          event,
            "actor":          actor,
            "correlation_id": session_id,
            "ts":             _now_iso(),
            "session_id":     session_id,
            "topic":          state.get("topic"),
            "source_system":  state.get("source_system"),
            "schema_grain":   state.get("schema_grain"),
            "job_key":        state.get("job_key"),
            "environment":    state.get("environment"),
            "branch_name":    state.get("branch_name"),
            "approved":       state.get("user_approved"),
            "pr_number":      pr_number,
            "pr_url":         pr_url,
            "error":          error,
        }
        _audit_logger.info(json.dumps(record))
    except Exception:
        pass
