"""
REST API routes — session management and health check endpoints.

Authentication model:
  POST /api/sessions   — server generates session_id + session_token (no auth required)
  GET  /api/sessions/{id}    — requires Authorization: Bearer <session_token>
  DELETE /api/sessions/{id}  — requires Authorization: Bearer <session_token>

The session_token must be presented by the same client that created the session.
WebSocket ownership is enforced in websocket.py via ?token= query parameter.
"""

import secrets
import uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.audit_log import log_event

router = APIRouter()


class NewSessionResponse(BaseModel):
    session_id: str
    session_token: str
    ws_url: str


class SessionStatusResponse(BaseModel):
    session_id: str
    current_step: str
    waiting_for_user: bool
    exists: bool


def _require_owner(session_id: str, authorization: str) -> None:
    """
    Extract Bearer token from Authorization header and verify ownership.
    Raises HTTP 403 if the token is absent, malformed, or does not match the session.
    
    NOTE: For Redis-backed registries, use _require_owner_async() instead.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Authorization header required")
    token = authorization[len("Bearer "):].strip()
    from app.models.session import get_session_registry, SessionRegistry
    registry = get_session_registry()
    if isinstance(registry, SessionRegistry) and not registry.validate_token(session_id, token):
        raise HTTPException(status_code=403, detail="Invalid or expired session token")


async def _require_owner_async(session_id: str, authorization: str) -> None:
    """
    Async version: Extract Bearer token and verify ownership (supports Redis).
    Raises HTTP 403 if the token is absent, malformed, or does not match the session.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Authorization header required")
    token = authorization[len("Bearer "):].strip()
    from app.models.session import get_session_registry, RedisSessionRegistry, SessionRegistry
    registry = get_session_registry()
    
    valid = False
    if isinstance(registry, RedisSessionRegistry):
        valid = await registry.validate_token(session_id, token)
    elif isinstance(registry, SessionRegistry):
        valid = registry.validate_token(session_id, token)
    
    if not valid:
        raise HTTPException(status_code=403, detail="Invalid or expired session token")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/sessions", response_model=NewSessionResponse)
async def create_session():
    """
    Create a new authenticated session.
    Returns a session_id and a cryptographically secure session_token.
    The client MUST store the token and present it on every subsequent request.
    """
    session_id = str(uuid.uuid4())
    # 32 bytes of CSPRNG output → 43-character URL-safe base64 string (256 bits entropy)
    session_token = secrets.token_urlsafe(32)
    from app.models.session import get_session_registry
    registry = get_session_registry()
    
    # Handle both sync and async registries
    from app.models.session import RedisSessionRegistry
    if isinstance(registry, RedisSessionRegistry):
        await registry.register(session_id, session_token)
    else:
        registry.register(session_id, session_token)
    
    log_event("session_created", "system", {"session_id": session_id})
    return NewSessionResponse(
        session_id=session_id,
        session_token=session_token,
        ws_url=f"/ws/{session_id}",
    )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    authorization: str = Header(default=""),
):
    """Get the current status of a session. Requires ownership token."""
    await _require_owner_async(session_id, authorization)

    from app.models.session import get_session_store
    store = get_session_store()
    state = await store.get(session_id)

    if state is None:
        return SessionStatusResponse(
            session_id=session_id,
            current_step="none",
            waiting_for_user=False,
            exists=False,
        )

    return SessionStatusResponse(
        session_id=session_id,
        current_step=state.get("current_step", "unknown"),
        waiting_for_user=state.get("waiting_for_user", False),
        exists=True,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    authorization: str = Header(default=""),
):
    """Delete a session (reset conversation). Requires ownership token."""
    await _require_owner_async(session_id, authorization)

    from app.models.session import get_session_store
    store = get_session_store()
    await store.delete(session_id)
    return {"deleted": True, "session_id": session_id}


# ── Draft Workspace endpoints (Step 2.2) ──────────────────────────────────────

@router.get("/sessions/{session_id}/draft")
async def get_draft_review(
    session_id: str,
    authorization: str = Header(default=""),
):
    """
    Return the draft workspace summary for the given session.

    Response shape (when ENABLE_DRAFT_WORKSPACE=True):
      {
        "draft_id": str,
        "session_id": str,
        "status": str,
        "files_count": int,
        "glue_jobs_count": int,
        "glue_jobs": [{job_key, source_system, schema_grain, created_at}],
        "snapshots_count": int,
        "create_another_job_visible": bool,   # True when glue_jobs_count > 0
        "created_at": datetime,
        "updated_at": datetime,
      }

    Returns 404 when the session has no draft (either feature flag off or session
    not yet initialised).
    """
    await _require_owner_async(session_id, authorization)

    from app.api.processor import get_session_draft_summary
    summary = get_session_draft_summary(session_id)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="No draft workspace found for this session. "
                   "Either ENABLE_DRAFT_WORKSPACE is off or the session has not been initialised.",
        )
    return summary


@router.post("/sessions/{session_id}/draft/discard")
async def discard_last_change(
    session_id: str,
    authorization: str = Header(default=""),
):
    """
    Discard the last change in the session's draft workspace (snapshot-based undo).

    Returns {"discarded": True} on success.
    Returns 409 when there is nothing to discard.
    Returns 404 when no draft exists for the session.
    """
    await _require_owner_async(session_id, authorization)

    from app.api.processor import get_session_draft_summary, discard_session_draft_change

    # Verify the draft exists before attempting discard
    summary = get_session_draft_summary(session_id)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="No draft workspace found for this session.",
        )

    success = discard_session_draft_change(session_id)
    if not success:
        raise HTTPException(
            status_code=409,
            detail="Nothing to discard — no undo history available.",
        )
    return {"discarded": True, "session_id": session_id}


class UpdateDraftMetaRequest(BaseModel):
    """STEP 2.3: Update user-editable draft metadata."""
    branch_name: str | None = None
    user_commit_message: str | None = None
    user_pr_title: str | None = None
    user_pr_description: str | None = None


@router.post("/sessions/{session_id}/draft/update_meta")
async def update_draft_meta(
    session_id: str,
    request: UpdateDraftMetaRequest,
    authorization: str = Header(default=""),
):
    """
    STEP 2.3: Update user-editable metadata for draft.

    Persists:
    - branch_name: Custom branch name (default: draft/<draft_id>)
    - user_commit_message: Custom commit message
    - user_pr_title: Custom PR title
    - user_pr_description: Custom PR description

    Returns the updated draft metadata.
    """
    await _require_owner_async(session_id, authorization)

    from app.api.processor import update_session_draft_metadata

    metadata = {k: v for k, v in request.dict().items() if v is not None}
    result = update_session_draft_metadata(session_id, metadata)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No draft workspace found for this session.",
        )

    return {"status": "success", "metadata": result}


@router.post("/sessions/{session_id}/draft/preview_commit")
async def preview_draft_commit(
    session_id: str,
    authorization: str = Header(default=""),
):
    """
    STEP 2.3: Compute diff/patch for all files in draft without committing.

    Returns preview of changes:
    {
      "draft_id": str,
      "files_count": int,
      "total_size": int (bytes),
      "file_list": [{ "path": str, "size": int, "type": str }]
    }
    """
    await _require_owner_async(session_id, authorization)

    from app.api.processor import preview_session_draft_commit

    preview = preview_session_draft_commit(session_id)
    if preview is None:
        raise HTTPException(
            status_code=404,
            detail="No draft workspace found for this session.",
        )

    return preview


@router.post("/sessions/{session_id}/draft/create_pr")
async def create_draft_pr(
    session_id: str,
    authorization: str = Header(default=""),
):
    """
    STEP 2.3: Trigger single-commit PR creation for draft.

    This endpoint:
    1. Marks draft as PR_CREATING (frozen, no more edits)
    2. Collects all files from draft
    3. Calls GitHubService.create_single_commit_and_pr()
    4. Returns PR URL + number

    Returns:
    {
      "status": "success",
      "pr_url": str,
      "pr_number": int,
      "commit_sha": str
    }

    Raises 409 if draft is already PR_CREATING (duplicate protection).
    """
    await _require_owner_async(session_id, authorization)

    from app.api.processor import create_session_draft_pr

    result = create_session_draft_pr(session_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No draft workspace found for this session.",
        )
    if "error" in result:
        raise HTTPException(
            status_code=409,
            detail=result["error"],
        )

    return result


@router.post("/sessions/{session_id}/draft/abandon")
async def abandon_draft(
    session_id: str,
    authorization: str = Header(default=""),
):
    """
    STEP 2.3: Mark draft as ABANDONED (read-only, no further edits).

    Returns {"status": "success"}.
    """
    await _require_owner_async(session_id, authorization)

    from app.api.processor import abandon_session_draft

    result = abandon_session_draft(session_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No draft workspace found for this session.",
        )

    return {"status": "success", "session_id": session_id}
