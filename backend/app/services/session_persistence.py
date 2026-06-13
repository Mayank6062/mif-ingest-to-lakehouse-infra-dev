"""
Session Persistence Service — Load, save, and restore sessions.

This module provides:
- SessionPersistenceService: high-level session API
- Session hydration (full state restore)
- Message history management
- Session lifecycle management
"""

import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.state_v2 import (
    Session,
    SessionStatus,
    DraftWorkspace,
    Message,
    NavigatorState,
    create_session,
    create_message,
)
from app.services.draft_workspace_service import DraftWorkspaceService


class SessionPersistenceService:
    """
    Persist and restore sessions.
    
    Usage:
    ```python
    service = SessionPersistenceService()
    
    # Create new session
    session = service.create_session("user@example.com", "dev")
    
    # Save session state
    service.save_session(session)
    
    # Restore session
    restored = service.restore_session(session_id)
    
    # Add message
    service.add_message(session, "assistant", "Hello!")
    ```
    """
    
    def __init__(self):
        """Initialize session persistence service."""
        self.draft_service = DraftWorkspaceService()
        
        # In-memory storage: session_id → Session
        self._sessions: Dict[str, Session] = {}
        # session_id → NavigatorState
        self._navigator_states: Dict[str, NavigatorState] = {}
    
    def create_session(
        self,
        user_email: str,
        environment: str = "dev",
        repository_url: str = "",
        base_branch: str = "main",
    ) -> Session:
        """
        Create a new session.
        
        Args:
            user_email: user's email
            environment: dev | snd | prod
            repository_url: GitHub repo URL
            base_branch: default branch to use
        
        Returns:
            New Session
        """
        session_id = str(uuid.uuid4())
        session = create_session(
            session_id=session_id,
            user_email=user_email,
            environment=environment,
            repository_url=repository_url,
            base_branch=base_branch,
        )
        
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve session by ID."""
        return self._sessions.get(session_id)
    
    def save_session(self, session: Session) -> None:
        """
        Persist session to storage (currently in-memory).
        
        Args:
            session: Session to save
        """
        session_id = session['session_id']
        session['updated_at'] = datetime.now()
        self._sessions[session_id] = session
    
    def restore_session(
        self,
        session_id: str,
    ) -> Optional[Session]:
        """
        Fully restore a session from storage.
        
        Hydrates:
        - Session metadata
        - Message history
        - Current draft workspace (if any)
        - Validation reports
        - NavigatorState
        
        Returns:
            Restored Session, or None if not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        session['last_activity_at'] = datetime.now()
        return session
    
    def add_message(
        self,
        session: Session,
        role: str,
        content: str,
        step_name: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Message:
        """
        Add a message to session history.
        
        Args:
            session: target session
            role: assistant | user | system
            content: message text
            step_name: which workflow step this message is from
            actions: attached action cards
        
        Returns:
            Created Message
        """
        message_id = str(uuid.uuid4())
        message = create_message(
            message_id=message_id,
            role=role,
            content=content,
            step_name=step_name,
            actions=actions or [],
        )
        
        session['message_history'].append(message)
        session['updated_at'] = datetime.now()
        
        return message
    
    def get_message_history(
        self,
        session: Session,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """
        Get message history for a session.
        
        Args:
            session: target session
            limit: max number of messages to return (most recent first)
        
        Returns:
            List of messages in reverse chronological order
        """
        history = list(reversed(session['message_history']))
        if limit:
            history = history[:limit]
        return history
    
    def create_draft_for_session(self, session: Session) -> DraftWorkspace:
        """
        Create a new draft workspace for a session.
        
        Args:
            session: target session
        
        Returns:
            New DraftWorkspace
        """
        draft = self.draft_service.create_draft(session['session_id'])
        session['current_draft_id'] = draft['draft_id']
        session['updated_at'] = datetime.now()
        return draft
    
    def get_current_draft(self, session: Session) -> Optional[DraftWorkspace]:
        """Get the current draft workspace for a session."""
        if not session['current_draft_id']:
            return None
        return self.draft_service.get_draft(session['current_draft_id'])
    
    def set_navigator_state(
        self,
        session: Session,
        navigator_state: NavigatorState,
    ) -> None:
        """Store navigator state for a session."""
        self._navigator_states[session['session_id']] = navigator_state
    
    def get_navigator_state(self, session: Session) -> Optional[NavigatorState]:
        """Retrieve navigator state for a session."""
        return self._navigator_states.get(session['session_id'])
    
    def update_status(
        self,
        session: Session,
        status: str,
    ) -> None:
        """
        Update session status.
        
        Args:
            session: target session
            status: active | paused | closed | pr_created | archived
        """
        session['status'] = status
        session['updated_at'] = datetime.now()
    
    def close_session(self, session: Session) -> None:
        """Mark session as closed."""
        session['status'] = SessionStatus.CLOSED
        session['updated_at'] = datetime.now()
    
    def archive_session(self, session: Session) -> None:
        """Mark session as archived (after PR merge)."""
        session['status'] = SessionStatus.ARCHIVED
        session['updated_at'] = datetime.now()
    
    def get_session_summary(self, session: Session) -> Dict[str, Any]:
        """Get high-level summary of session."""
        current_draft = self.get_current_draft(session)
        
        return {
            'session_id': session['session_id'],
            'user_email': session['user_email'],
            'status': session['status'],
            'environment': session['environment'],
            'message_count': len(session['message_history']),
            'current_draft_id': session['current_draft_id'],
            'current_draft_status': current_draft['status'] if current_draft else None,
            'created_at': session['created_at'],
            'updated_at': session['updated_at'],
            'last_activity_at': session['last_activity_at'],
        }
    
    def list_all_sessions(self) -> List[Session]:
        """Get all sessions (for admin/testing)."""
        return list(self._sessions.values())
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all associated data.
        
        Returns:
            True if deleted, False if not found
        """
        if session_id not in self._sessions:
            return False
        
        session = self._sessions[session_id]
        
        # Clean up draft if exists
        if session['current_draft_id']:
            draft = self.draft_service.get_draft(session['current_draft_id'])
            if draft:
                self.draft_service.mark_abandoned(draft)
        
        # Clean up navigator state
        self._navigator_states.pop(session_id, None)
        
        # Remove session
        del self._sessions[session_id]
        
        return True
    
    def export_session_to_json(self, session: Session) -> str:
        """Export session as JSON (for debugging/logging)."""
        try:
            export_dict = {
                'session_id': session['session_id'],
                'user_email': session['user_email'],
                'status': session['status'],
                'environment': session['environment'],
                'message_count': len(session['message_history']),
                'created_at': session['created_at'].isoformat() if session['created_at'] else None,
                'updated_at': session['updated_at'].isoformat() if session['updated_at'] else None,
                'last_activity_at': session['last_activity_at'].isoformat() if session['last_activity_at'] else None,
            }
            return json.dumps(export_dict, indent=2)
        except Exception as e:
            return json.dumps({'error': str(e)})
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        return sum(
            1 for s in self._sessions.values()
            if s['status'] == SessionStatus.ACTIVE
        )
    
    def cleanup_inactive_sessions(self, ttl_seconds: int = 86400) -> int:
        """
        Delete sessions inactive for TTL seconds.
        
        Args:
            ttl_seconds: time-to-live (default 24 hours)
        
        Returns:
            Count of deleted sessions
        """
        now = datetime.now()
        to_delete = []
        
        for session_id, session in self._sessions.items():
            last_activity = session['last_activity_at']
            age = (now - last_activity).total_seconds()
            
            if age > ttl_seconds:
                to_delete.append(session_id)
        
        for session_id in to_delete:
            self.delete_session(session_id)
        
        return len(to_delete)
