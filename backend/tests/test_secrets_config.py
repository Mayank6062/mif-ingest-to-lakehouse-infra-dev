"""
Unit tests for SEC-003 Secret Hardening.

Covers:
  - SecretStr field types on Settings
  - str()/repr() masking of secrets
  - get_secret_value() unwrapping
  - Startup validation (all required fields)
  - llm_service callsite passes str not SecretStr to AzureOpenAI
  - github_service callsite passes str not SecretStr to Github
  - get_settings.cache_clear() isolation
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ── Cache isolation helper ────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear the lru_cache on get_settings() before and after every test."""
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_settings(**overrides):
    """
    Build a Settings instance with sensible test values, optionally overridden.
    Uses monkeypatching via environment variables so lru_cache is bypassed.
    """
    base_env = {
        "AZURE_OPENAI_API_KEY": "test-openai-key-abc123",
        "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1-mini",
        "AZURE_OPENAI_API_VERSION": "2024-02-01",
        "GITHUB_TOKEN": "github_pat_testtoken123",
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


# ─────────────────────────────────────────────────────────────────────────────
# SecretStr field types
# ─────────────────────────────────────────────────────────────────────────────

class TestSecretStrFieldTypes:
    def test_azure_openai_api_key_is_secret_str(self):
        from pydantic import SecretStr
        s = _make_settings()
        assert isinstance(s.azure_openai_api_key, SecretStr), (
            "azure_openai_api_key must be SecretStr, not plain str"
        )

    def test_github_token_is_secret_str(self):
        from pydantic import SecretStr
        s = _make_settings()
        assert isinstance(s.github_token, SecretStr), (
            "github_token must be SecretStr, not plain str"
        )

    def test_non_secret_fields_remain_plain_str(self):
        s = _make_settings()
        assert isinstance(s.azure_openai_endpoint, str)
        assert isinstance(s.github_repo_owner, str)
        assert isinstance(s.knowledge_base_path, str)


# ─────────────────────────────────────────────────────────────────────────────
# SecretStr masking — str() and repr()
# ─────────────────────────────────────────────────────────────────────────────

class TestSecretStrMasking:
    def test_str_of_api_key_does_not_contain_raw_value(self):
        s = _make_settings(azure_openai_api_key="supersecretkey999")
        # str() of a SecretStr should return masked output, never the raw value
        assert "supersecretkey999" not in str(s.azure_openai_api_key), (
            "str(azure_openai_api_key) must not expose the raw secret"
        )

    def test_repr_of_api_key_does_not_contain_raw_value(self):
        s = _make_settings(azure_openai_api_key="supersecretkey999")
        assert "supersecretkey999" not in repr(s.azure_openai_api_key), (
            "repr(azure_openai_api_key) must not expose the raw secret"
        )

    def test_str_of_github_token_does_not_contain_raw_value(self):
        s = _make_settings(github_token="github_pat_realtoken999")
        assert "github_pat_realtoken999" not in str(s.github_token), (
            "str(github_token) must not expose the raw secret"
        )

    def test_repr_of_github_token_does_not_contain_raw_value(self):
        s = _make_settings(github_token="github_pat_realtoken999")
        assert "github_pat_realtoken999" not in repr(s.github_token), (
            "repr(github_token) must not expose the raw secret"
        )

    def test_settings_model_dump_masks_secrets(self):
        """model_dump() on Settings must not return raw secret values."""
        s = _make_settings(
            azure_openai_api_key="openai-secret-xyz",
            github_token="gh-token-secret-xyz",
        )
        dumped = s.model_dump()
        # Pydantic SecretStr appears as the SecretStr wrapper, not raw string
        # The raw value is NOT a str in the dumped dict
        api_key_val = dumped.get("azure_openai_api_key")
        gh_token_val = dumped.get("github_token")
        # Neither should be a plain str containing the secret
        assert str(api_key_val) != "openai-secret-xyz", (
            "model_dump() must not expose raw azure_openai_api_key"
        )
        assert str(gh_token_val) != "gh-token-secret-xyz", (
            "model_dump() must not expose raw github_token"
        )

    def test_str_masking_output_format(self):
        """Pydantic SecretStr masks with '**********' in str() output."""
        from pydantic import SecretStr
        s = _make_settings(azure_openai_api_key="mykey")
        masked = str(s.azure_openai_api_key)
        # Must contain asterisks or similar masking indicator
        assert "**" in masked or "secret" in masked.lower(), (
            f"Expected masking in str(SecretStr), got: {masked!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# get_secret_value() — unwrapping
# ─────────────────────────────────────────────────────────────────────────────

class TestGetSecretValue:
    def test_api_key_get_secret_value_returns_actual_key(self):
        s = _make_settings(azure_openai_api_key="myrealapikey")
        assert s.azure_openai_api_key.get_secret_value() == "myrealapikey"

    def test_github_token_get_secret_value_returns_actual_token(self):
        s = _make_settings(github_token="github_pat_mytoken")
        assert s.github_token.get_secret_value() == "github_pat_mytoken"

    def test_empty_secret_returns_empty_string(self):
        s = _make_settings(azure_openai_api_key="")
        assert s.azure_openai_api_key.get_secret_value() == ""


# ─────────────────────────────────────────────────────────────────────────────
# Startup validation
# ─────────────────────────────────────────────────────────────────────────────

class TestStartupValidation:
    def _run_validation(self, settings):
        """Call the startup validator directly."""
        from app.main import _validate_required_config
        _validate_required_config(settings)

    def test_all_required_fields_present_passes(self):
        s = _make_settings()
        # Should not raise
        self._run_validation(s)

    def test_missing_azure_openai_api_key_raises(self):
        s = _make_settings(azure_openai_api_key="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        assert "AZURE_OPENAI_API_KEY" in str(exc_info.value)

    def test_missing_azure_openai_endpoint_raises(self):
        s = _make_settings(azure_openai_endpoint="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        assert "AZURE_OPENAI_ENDPOINT" in str(exc_info.value)

    def test_missing_github_token_raises(self):
        s = _make_settings(github_token="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        assert "GITHUB_TOKEN" in str(exc_info.value)

    def test_missing_github_repo_owner_raises(self):
        s = _make_settings(github_repo_owner="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        assert "GITHUB_REPO_OWNER" in str(exc_info.value)

    def test_missing_github_repo_name_raises(self):
        s = _make_settings(github_repo_name="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        assert "GITHUB_REPO_NAME" in str(exc_info.value)

    def test_multiple_missing_fields_reports_all(self):
        s = _make_settings(azure_openai_api_key="", github_token="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        msg = str(exc_info.value)
        assert "AZURE_OPENAI_API_KEY" in msg
        assert "GITHUB_TOKEN" in msg

    def test_error_message_does_not_contain_secret_value(self):
        """Error messages must never print the actual secret values."""
        s = _make_settings(github_token="")
        with pytest.raises(RuntimeError) as exc_info:
            self._run_validation(s)
        # The error message should not contain other actual secret values
        # (azure_openai_api_key is valid and should not appear in error)
        assert "test-openai-key-abc123" not in str(exc_info.value)


# ─────────────────────────────────────────────────────────────────────────────
# llm_service callsite — passes str not SecretStr to AzureOpenAI
# ─────────────────────────────────────────────────────────────────────────────

class TestLLMServiceCallsite:
    def test_get_llm_client_passes_str_api_key(self):
        """AzureOpenAI must receive a plain str api_key, not SecretStr."""
        import app.services.llm_service as svc
        # Reset module-level singleton
        svc._client = None

        captured_kwargs = {}

        class FakeAzureOpenAI:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key-for-llm",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "AZURE_OPENAI_API_VERSION": "2024-02-01",
            "GITHUB_TOKEN": "gh_test",
            "GITHUB_REPO_OWNER": "owner",
            "GITHUB_REPO_NAME": "repo",
        }, clear=True):
            with patch("app.services.llm_service.AzureOpenAI", FakeAzureOpenAI):
                svc._client = None
                svc.get_llm_client()

        api_key = captured_kwargs.get("api_key")
        assert isinstance(api_key, str), (
            f"AzureOpenAI api_key must be plain str, got {type(api_key)}"
        )
        assert api_key == "test-key-for-llm", (
            "AzureOpenAI must receive the unwrapped secret value"
        )
        # Cleanup
        svc._client = None

    def test_get_llm_client_api_key_is_not_secret_str(self):
        """Confirm SecretStr is NOT passed through to the SDK."""
        from pydantic import SecretStr
        import app.services.llm_service as svc
        svc._client = None

        captured_kwargs = {}

        class FakeAzureOpenAI:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "another-test-key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "AZURE_OPENAI_API_VERSION": "2024-02-01",
            "GITHUB_TOKEN": "gh_test",
            "GITHUB_REPO_OWNER": "owner",
            "GITHUB_REPO_NAME": "repo",
        }, clear=True):
            with patch("app.services.llm_service.AzureOpenAI", FakeAzureOpenAI):
                svc._client = None
                svc.get_llm_client()

        api_key = captured_kwargs.get("api_key")
        assert not isinstance(api_key, SecretStr), (
            "AzureOpenAI must NOT receive a SecretStr — SDK expects plain str"
        )
        svc._client = None


# ─────────────────────────────────────────────────────────────────────────────
# github_service callsite — passes str not SecretStr to Github
# ─────────────────────────────────────────────────────────────────────────────

class TestGitHubServiceCallsite:
    def test_github_service_passes_str_token(self):
        """Github() must receive a plain str token, not SecretStr."""
        from pydantic import SecretStr

        captured_args = []

        class FakeGithub:
            def __init__(self, *args, **kwargs):
                captured_args.extend(args)

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "github_pat_testtoken_abc",
            "GITHUB_REPO_OWNER": "test-owner",
            "GITHUB_REPO_NAME": "test-repo",
            "GITHUB_BASE_BRANCH": "main",
        }, clear=True):
            with patch("app.services.github_service.Github", FakeGithub):
                from app.services.github_service import GitHubService
                GitHubService()

        assert len(captured_args) >= 1, "Github() was not called with any arguments"
        token_arg = captured_args[0]
        assert isinstance(token_arg, str), (
            f"Github() must receive plain str token, got {type(token_arg)}"
        )
        assert not isinstance(token_arg, SecretStr), (
            "Github() must NOT receive SecretStr"
        )
        assert token_arg == "github_pat_testtoken_abc", (
            "Github() must receive the unwrapped secret value"
        )

    def test_github_service_token_value_is_correct(self):
        """The token passed to Github() must be the actual secret value."""
        captured_args = []

        class FakeGithub:
            def __init__(self, *args, **kwargs):
                captured_args.extend(args)

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "my-specific-test-token",
            "GITHUB_REPO_OWNER": "test-owner",
            "GITHUB_REPO_NAME": "test-repo",
            "GITHUB_BASE_BRANCH": "main",
        }, clear=True):
            with patch("app.services.github_service.Github", FakeGithub):
                from app.services.github_service import GitHubService
                GitHubService()

        assert captured_args[0] == "my-specific-test-token"


# ─────────────────────────────────────────────────────────────────────────────
# get_settings() lru_cache isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestSettingsCacheIsolation:
    def test_get_settings_returns_same_instance(self):
        """lru_cache means successive calls return identical object."""
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "key1",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "token1",
            "GITHUB_REPO_OWNER": "owner",
            "GITHUB_REPO_NAME": "repo",
        }, clear=True):
            from app.config import get_settings
            s1 = get_settings()
            s2 = get_settings()
            assert s1 is s2, "get_settings() must return the cached instance"

    def test_cache_clear_allows_reloading_new_values(self):
        """After cache_clear(), new env var values are picked up."""
        from app.config import get_settings

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "first-key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "first-token",
            "GITHUB_REPO_OWNER": "owner",
            "GITHUB_REPO_NAME": "repo",
        }, clear=True):
            s1 = get_settings()
            val1 = s1.azure_openai_api_key.get_secret_value()

        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "second-key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "second-token",
            "GITHUB_REPO_OWNER": "owner",
            "GITHUB_REPO_NAME": "repo",
        }, clear=True):
            s2 = get_settings()
            val2 = s2.azure_openai_api_key.get_secret_value()

        assert val1 == "first-key"
        assert val2 == "second-key"
        assert s1 is not s2, "After cache_clear(), a new Settings instance must be created"

    def test_settings_are_not_same_after_cache_clear(self):
        """Object identity changes after cache_clear()."""
        from app.config import get_settings

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "tok",
            "GITHUB_REPO_OWNER": "o",
            "GITHUB_REPO_NAME": "r",
        }, clear=True):
            s1 = get_settings()

        get_settings.cache_clear()

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "key",
            "AZURE_OPENAI_ENDPOINT": "https://ai-proxy.lab.epam.com",
            "GITHUB_TOKEN": "tok",
            "GITHUB_REPO_OWNER": "o",
            "GITHUB_REPO_NAME": "r",
        }, clear=True):
            s2 = get_settings()

        assert s1 is not s2
