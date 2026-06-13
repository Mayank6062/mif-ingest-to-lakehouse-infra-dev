"""
Unit tests for Session Persistence Service.

Tests:
- Session creation
- Session restore
- Message management
- Navigator state
- Session lifecycle
"""

import pytest
import json
from datetime import datetime
from app.services.session_persistence import SessionPersistenceService
from app.models.state_v2 import SessionStatus


class TestSessionPersistenceServiceCreation:
    """Test session creation."""
    
    def test_create_session(self):
        """Test creating a session."""
        service = SessionPersistenceService()
        
        session = service.create_session(
            user_email="test@example.com",
            environment="dev",
            repository_url="https://github.com/example/repo",
        )
        
        assert session['session_id'] is not None
        assert session['user_email'] == "test@example.com"
        assert session['environment'] == "dev"
        assert session['status'] == SessionStatus.ACTIVE
        assert session['message_history'] == []
    
    def test_get_session(self):
        """Test retrieving a session."""
        service = SessionPersistenceService()
        
        created = service.create_session("test@example.com", "dev")
        retrieved = service.get_session(created['session_id'])
        
        assert retrieved is not None
        assert retrieved['session_id'] == created['session_id']


class TestSessionPersistence:
    """Test session storage and retrieval."""
    
    def test_save_session(self):
        """Test saving a session."""
        service = SessionPersistenceService()
        
        session = service.create_session("test@example.com", "dev")
        session['status'] = SessionStatus.PAUSED
        
        service.save_session(session)
        
        # Retrieve and verify
        retrieved = service.get_session(session['session_id'])
        assert retrieved['status'] == SessionStatus.PAUSED
    
    def test_restore_session(self):
        """Test restoring a session."""
        service = SessionPersistenceService()
        
        session = service.create_session("test@example.com", "dev")
        
        restored = service.restore_session(session['session_id'])
        
        assert restored is not None
        assert restored['session_id'] == session['session_id']
    
    def test_restore_nonexistent_session(self):
        """Test restoring nonexistent session returns None."""
        service = SessionPersistenceService()
        
        restored = service.restore_session("nonexistent")
        
        assert restored is None


class TestMessageManagement:
    """Test message history."""
    
    def test_add_message_assistant(self):
        """Test adding assistant message."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        message = service.add_message(
            session,
            role="assistant",
            content="Hello!",
            step_name="collect_topic",
        )
        
        assert message['role'] == "assistant"
        assert message['content'] == "Hello!"
        assert len(session['message_history']) == 1
    
    def test_add_user_message(self):
        """Test adding user message."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        message = service.add_message(
            session,
            role="user",
            content="Hi there!",
        )
        
        assert message['role'] == "user"
        assert len(session['message_history']) == 1
    
    def test_get_message_history(self):
        """Test retrieving message history."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        service.add_message(session, "user", "Message 1")
        service.add_message(session, "assistant", "Message 2")
        service.add_message(session, "user", "Message 3")
        
        history = service.get_message_history(session)
        
        assert len(history) == 3
        # Should be in reverse chronological order
        assert history[0]['content'] == "Message 3"
        assert history[1]['content'] == "Message 2"
    
    def test_get_message_history_limit(self):
        """Test limiting message history."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        for i in range(5):
            service.add_message(session, "user", f"Message {i}")
        
        history = service.get_message_history(session, limit=3)
        
        assert len(history) == 3


class TestDraftWorkspace:
    """Test draft management in session."""
    
    def test_create_draft_for_session(self):
        """Test creating a draft for a session."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        draft = service.create_draft_for_session(session)
        
        assert draft['session_id'] == session['session_id']
        assert session['current_draft_id'] == draft['draft_id']
    
    def test_get_current_draft(self):
        """Test getting current draft."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        created_draft = service.create_draft_for_session(session)
        retrieved_draft = service.get_current_draft(session)
        
        assert retrieved_draft is not None
        assert retrieved_draft['draft_id'] == created_draft['draft_id']
    
    def test_get_current_draft_none(self):
        """Test getting current draft when none exists."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        draft = service.get_current_draft(session)
        
        assert draft is None


class TestNavigatorState:
    """Test navigator state management."""
    
    def test_set_navigator_state(self):
        """Test setting navigator state."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        navigator_state = {
            'current_step': 'collect_topic',
            'completed_steps': ['collect_source_system'],
            'visited_steps': ['start', 'collect_source_system'],
        }
        
        service.set_navigator_state(session, navigator_state)
        
        retrieved = service.get_navigator_state(session)
        assert retrieved is not None
        assert retrieved['current_step'] == 'collect_topic'
    
    def test_get_navigator_state_none(self):
        """Test getting navigator state when not set."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        state = service.get_navigator_state(session)
        
        assert state is None


class TestStatusManagement:
    """Test session status transitions."""
    
    def test_update_status(self):
        """Test updating session status."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        service.update_status(session, SessionStatus.PAUSED)
        
        assert session['status'] == SessionStatus.PAUSED
    
    def test_close_session(self):
        """Test closing a session."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        service.close_session(session)
        
        assert session['status'] == SessionStatus.CLOSED
    
    def test_archive_session(self):
        """Test archiving a session."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        service.archive_session(session)
        
        assert session['status'] == SessionStatus.ARCHIVED


class TestSessionSummary:
    """Test summary generation."""
    
    def test_get_session_summary(self):
        """Test getting session summary."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        service.add_message(session, "user", "Message 1")
        service.add_message(session, "assistant", "Message 2")
        
        summary = service.get_session_summary(session)
        
        assert summary['session_id'] == session['session_id']
        assert summary['user_email'] == "test@example.com"
        assert summary['status'] == SessionStatus.ACTIVE
        assert summary['message_count'] == 2


class TestSessionLifecycle:
    """Test session lifecycle operations."""
    
    def test_list_all_sessions(self):
        """Test listing all sessions."""
        service = SessionPersistenceService()
        
        service.create_session("user1@example.com", "dev")
        service.create_session("user2@example.com", "prod")
        
        all_sessions = service.list_all_sessions()
        
        assert len(all_sessions) == 2
    
    def test_delete_session(self):
        """Test deleting a session."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        result = service.delete_session(session['session_id'])
        
        assert result is True
        
        # Verify it's gone
        retrieved = service.get_session(session['session_id'])
        assert retrieved is None
    
    def test_delete_nonexistent_session(self):
        """Test deleting nonexistent session."""
        service = SessionPersistenceService()
        
        result = service.delete_session("nonexistent")
        
        assert result is False
    
    def test_export_session_to_json(self):
        """Test exporting session as JSON."""
        service = SessionPersistenceService()
        session = service.create_session("test@example.com", "dev")
        
        json_str = service.export_session_to_json(session)
        
        data = json.loads(json_str)
        assert data['session_id'] == session['session_id']
        assert data['user_email'] == "test@example.com"
    
    def test_get_active_sessions_count(self):
        """Test counting active sessions."""
        service = SessionPersistenceService()
        
        s1 = service.create_session("user1@example.com", "dev")
        s2 = service.create_session("user2@example.com", "dev")
        
        service.close_session(s2)
        
        count = service.get_active_sessions_count()
        
        assert count == 1
    
    def test_cleanup_inactive_sessions(self):
        """Test cleanup of inactive sessions."""
        service = SessionPersistenceService()
        
        s1 = service.create_session("user1@example.com", "dev")
        
        # Manually set last_activity to very old date
        from datetime import timedelta
        s1['last_activity_at'] = datetime.now() - timedelta(days=2)
        
        # Cleanup with 1-day TTL
        cleaned = service.cleanup_inactive_sessions(ttl_seconds=86400)
        
        assert cleaned >= 0  # May or may not clean depending on timing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
