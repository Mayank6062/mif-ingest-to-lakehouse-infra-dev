"""
Tests for STEP 21 — LangSmith Observability.

Covers:
  A. Config: LangSmith settings fields (types, defaults, SecretStr for API key)
  B. Startup: _configure_langsmith() env var injection and clearing behaviour
  C. Thread config: _thread_config() enrichment (action, metadata, tags, run_name)
  D. LLM service: @traceable decorator applied, chat_complete behaviour unchanged
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ── Cache isolation ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear lru_caches before and after every test for isolation."""
    from app.config import get_settings
    from langsmith.utils import get_env_var
    get_settings.cache_clear()
    get_env_var.cache_clear()
    yield
    get_settings.cache_clear()
    get_env_var.cache_clear()


def _make_settings(**overrides):
    """
    Build a Settings instance with sensible test values, optionally overridden.
    Keyword args are uppercased and injected as env vars; the Settings object
    is constructed inside a clean env context.
    """
    base_env = {
        "AZURE_OPENAI_API_KEY": "test-openai-key",
        "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1-mini",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
        "GITHUB_TOKEN": "github_pat_test",
        "GITHUB_REPO_OWNER": "test-owner",
        "GITHUB_REPO_NAME": "test-repo",
        "GITHUB_BASE_BRANCH": "main",
        "KNOWLEDGE_BASE_PATH": "./knowledge_base",
        "SESSION_STORE_TTL_SECONDS": "3600",
        "CORS_ORIGINS": "http://localhost:3000",
    }
    base_env.update({k.upper(): v for k, v in overrides.items()})
    with patch.dict(os.environ, base_env, clear=True):
        from app.config import Settings
        return Settings()


# ── A. Config ─────────────────────────────────────────────────────────────────

class TestLangSmithConfig:
    def test_langsmith_api_key_is_secret_str(self):
        from pydantic import SecretStr
        s = _make_settings()
        assert isinstance(s.langsmith_api_key, SecretStr), (
            "langsmith_api_key must be SecretStr, not plain str"
        )

    def test_langsmith_api_key_str_does_not_expose_secret(self):
        s = _make_settings(langsmith_api_key="ls-super-secret-key-xyz")
        assert "ls-super-secret-key-xyz" not in str(s.langsmith_api_key), (
            "str(langsmith_api_key) must not expose the raw secret"
        )

    def test_langsmith_api_key_repr_does_not_expose_secret(self):
        s = _make_settings(langsmith_api_key="ls-super-secret-key-xyz")
        assert "ls-super-secret-key-xyz" not in repr(s.langsmith_api_key), (
            "repr(langsmith_api_key) must not expose the raw secret"
        )

    def test_langsmith_api_key_get_secret_value_returns_key(self):
        s = _make_settings(langsmith_api_key="ls-my-real-key")
        assert s.langsmith_api_key.get_secret_value() == "ls-my-real-key"

    def test_langsmith_api_key_default_is_empty(self):
        s = _make_settings()
        assert s.langsmith_api_key.get_secret_value() == ""

    def test_langsmith_project_default(self):
        s = _make_settings()
        assert s.langsmith_project == "glue-job-agent"

    def test_langsmith_tracing_disabled_by_default(self):
        s = _make_settings()
        assert s.langsmith_tracing_enabled is False

    def test_langsmith_tracing_can_be_enabled_via_env(self):
        s = _make_settings(langsmith_tracing_enabled="true")
        assert s.langsmith_tracing_enabled is True

    def test_langsmith_project_can_be_overridden(self):
        s = _make_settings(langsmith_project="custom-project")
        assert s.langsmith_project == "custom-project"


# ── B. Startup ────────────────────────────────────────────────────────────────

_LS_VARS = (
    "LANGSMITH_TRACING_V2", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT",
    "LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT",
)


class TestConfigureLangSmith:
    def _clean_ls_env(self):
        """Remove all LangSmith/LangChain tracing vars from os.environ."""
        for k in _LS_VARS:
            os.environ.pop(k, None)

    def test_env_vars_set_when_enabled_with_key(self):
        s = _make_settings(
            langsmith_api_key="ls-key-abc123",
            langsmith_project="my-project",
            langsmith_tracing_enabled="true",
        )
        from app.main import _configure_langsmith
        with patch.dict(os.environ, {}, clear=False):
            self._clean_ls_env()
            _configure_langsmith(s)
            assert os.environ.get("LANGSMITH_TRACING_V2") == "true"
            assert os.environ.get("LANGSMITH_API_KEY") == "ls-key-abc123"
            assert os.environ.get("LANGSMITH_PROJECT") == "my-project"

    def test_env_vars_not_set_when_tracing_disabled(self):
        s = _make_settings(
            langsmith_api_key="ls-key-abc123",
            langsmith_tracing_enabled="false",
        )
        from app.main import _configure_langsmith
        with patch.dict(os.environ, {"LANGSMITH_TRACING_V2": "true"}, clear=False):
            _configure_langsmith(s)
            assert os.environ.get("LANGSMITH_TRACING_V2") is None

    def test_env_vars_not_set_when_key_is_empty(self):
        s = _make_settings(
            langsmith_api_key="",
            langsmith_tracing_enabled="true",
        )
        from app.main import _configure_langsmith
        with patch.dict(os.environ, {}, clear=False):
            self._clean_ls_env()
            _configure_langsmith(s)
            assert os.environ.get("LANGSMITH_TRACING_V2") is None

    def test_startup_message_contains_enabled(self, capsys):
        s = _make_settings(
            langsmith_api_key="ls-key-xyz",
            langsmith_tracing_enabled="true",
        )
        from app.main import _configure_langsmith
        with patch.dict(os.environ, {}, clear=False):
            self._clean_ls_env()
            _configure_langsmith(s)
            captured = capsys.readouterr()
            assert "enabled" in captured.out.lower()

    def test_startup_message_contains_disabled(self, capsys):
        s = _make_settings(langsmith_tracing_enabled="false")
        from app.main import _configure_langsmith
        with patch.dict(os.environ, {}, clear=False):
            _configure_langsmith(s)
            captured = capsys.readouterr()
            assert "disabled" in captured.out.lower()

    def test_startup_message_never_contains_api_key(self, capsys):
        s = _make_settings(
            langsmith_api_key="very-secret-ls-key-789",
            langsmith_tracing_enabled="true",
        )
        from app.main import _configure_langsmith
        with patch.dict(os.environ, {}, clear=False):
            self._clean_ls_env()
            _configure_langsmith(s)
            captured = capsys.readouterr()
            assert "very-secret-ls-key-789" not in captured.out, (
                "API key must never appear in startup output"
            )

    def test_stale_langchain_vars_cleared_when_disabled(self):
        s = _make_settings(langsmith_tracing_enabled="false")
        from app.main import _configure_langsmith
        stale = {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "old-stale-key",
        }
        with patch.dict(os.environ, stale, clear=False):
            _configure_langsmith(s)
            assert os.environ.get("LANGCHAIN_TRACING_V2") is None, (
                "Stale LANGCHAIN_TRACING_V2 must be cleared when tracing is disabled"
            )
            assert os.environ.get("LANGCHAIN_API_KEY") is None, (
                "Stale LANGCHAIN_API_KEY must be cleared when tracing is disabled"
            )


# ── C. Thread Config ──────────────────────────────────────────────────────────

class TestThreadConfig:
    """_thread_config() enriches the LangGraph config with metadata, tags, run_name."""

    def _tc(self, session_id: str, **kwargs) -> dict:
        from app.api.processor import _thread_config
        return _thread_config(session_id, **kwargs)

    def test_thread_id_preserved(self):
        sid = "abc12345-1234-5678-abcd-abcdef123456"
        tc = self._tc(sid)
        assert tc["configurable"]["thread_id"] == sid

    def test_default_action_is_step(self):
        tc = self._tc("some-session-id")
        assert tc["metadata"]["action"] == "step"
        assert "step" in tc["tags"]

    def test_action_new(self):
        tc = self._tc("some-session-id", action="new")
        assert tc["metadata"]["action"] == "new"
        assert "new" in tc["tags"]

    def test_action_restart(self):
        tc = self._tc("some-session-id", action="restart")
        assert tc["metadata"]["action"] == "restart"
        assert "restart" in tc["tags"]

    def test_action_edit(self):
        tc = self._tc("some-session-id", action="edit")
        assert tc["metadata"]["action"] == "edit"
        assert "edit" in tc["tags"]

    def test_metadata_contains_session_id(self):
        sid = "deadbeef-0000-0000-0000-000000000000"
        tc = self._tc(sid)
        assert tc["metadata"]["session_id"] == sid

    def test_tags_contains_glue_job_agent(self):
        tc = self._tc("some-session-id")
        assert "glue-job-agent" in tc["tags"]

    def test_run_name_format(self):
        sid = "deadbeef-0000-0000-0000-000000000000"
        tc = self._tc(sid)
        assert tc["run_name"] == f"glue-job-{sid[:8]}"

    def test_run_name_uses_first_8_chars(self):
        sid = "12345678-abcd-efgh-ijkl-mnopqrstuvwx"
        tc = self._tc(sid)
        assert tc["run_name"] == "glue-job-12345678"

    def test_configurable_contains_only_thread_id(self):
        """configurable must not gain extra keys that could confuse LangGraph."""
        tc = self._tc("some-session-id")
        assert set(tc["configurable"].keys()) == {"thread_id"}

    def test_all_required_keys_present(self):
        tc = self._tc("some-session-id")
        assert "configurable" in tc
        assert "metadata" in tc
        assert "tags" in tc
        assert "run_name" in tc


# ── D. LLM Service @traceable ─────────────────────────────────────────────────

class TestLLMServiceTraceable:

    def test_chat_complete_has_wrapped_attribute(self):
        """`@traceable` applies `functools.wraps` — `__wrapped__` points to original."""
        from app.services.llm_service import chat_complete
        assert hasattr(chat_complete, "__wrapped__"), (
            "chat_complete must have __wrapped__ set by @traceable"
        )

    def test_chat_complete_name_preserved(self):
        """`functools.wraps` preserves `__name__` on the traceable wrapper."""
        from app.services.llm_service import chat_complete
        assert chat_complete.__name__ == "chat_complete"

    def test_chat_complete_returns_response_text(self):
        """@traceable does not change the return value of chat_complete."""
        import app.services.llm_service as svc
        svc._client = None  # reset singleton

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "llm reply"
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        disabled = {"LANGSMITH_TRACING_V2": "false", "LANGCHAIN_TRACING_V2": "false"}
        with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
            with patch.dict(os.environ, disabled, clear=False):
                result = svc.chat_complete([{"role": "user", "content": "hello"}])

        assert result == "llm reply"

    def test_chat_complete_with_system_prompt(self):
        """System prompt is prepended as the first message after @traceable."""
        import app.services.llm_service as svc
        svc._client = None

        captured_messages = []

        def _capture(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            r = MagicMock()
            r.choices[0].message.content = "reply"
            return r

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _capture

        disabled = {"LANGSMITH_TRACING_V2": "false", "LANGCHAIN_TRACING_V2": "false"}
        with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
            with patch.dict(os.environ, disabled, clear=False):
                result = svc.chat_complete(
                    [{"role": "user", "content": "hello"}],
                    system_prompt="you are helpful",
                )

        assert result == "reply"
        assert captured_messages[0] == {"role": "system", "content": "you are helpful"}
        assert captured_messages[1] == {"role": "user", "content": "hello"}

    def test_chat_complete_none_content_returns_empty_string(self):
        """None content from OpenAI response is converted to '' unchanged."""
        import app.services.llm_service as svc
        svc._client = None

        mock_response = MagicMock()
        mock_response.choices[0].message.content = None
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        disabled = {"LANGSMITH_TRACING_V2": "false", "LANGCHAIN_TRACING_V2": "false"}
        with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
            with patch.dict(os.environ, disabled, clear=False):
                result = svc.chat_complete([{"role": "user", "content": "hi"}])

        assert result == ""
