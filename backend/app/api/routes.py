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
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Authorization header required")
    token = authorization[len("Bearer "):].strip()
    from app.models.session import get_session_registry
    if not get_session_registry().validate_token(session_id, token):
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
    get_session_registry().register(session_id, session_token)
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
    _require_owner(session_id, authorization)

    from app.models.session import get_session_store
    store = get_session_store()
    state = store.get(session_id)

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
    _require_owner(session_id, authorization)

    from app.models.session import get_session_store
    store = get_session_store()
    await store.delete(session_id)
    return {"deleted": True, "session_id": session_id}
