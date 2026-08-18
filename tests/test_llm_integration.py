"""
test_llm_integration.py
=======================
Lightweight tests for the LiteLLM key-propagation layer and the mock-mode
guard introduced in this PR.

These tests do NOT make any real LLM API calls; they verify only:
  1. That ``settings.is_mock_mode`` behaves correctly in the default
     (no real key configured) environment used by CI.
  2. That importing ``llm_client`` pushes keys into ``os.environ`` when
     real keys ARE present, and leaves the env clean when they are not.

The existing 14 tests in test_router.py are unchanged.
"""

import os
import importlib
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# 1. Mock-mode guard
# ---------------------------------------------------------------------------

def test_mock_mode_is_default():
    """
    settings.is_mock_mode must be True in the default test environment
    (i.e., when no real provider key is set).
    """
    from backend.app.core.config import settings

    # Sanity-check the placeholder values used in CI
    assert settings.OPENAI_API_KEY    in ("", "mock-openai-key"),    \
        "OPENAI_API_KEY is set to a real value — is_mock_mode will be False in CI"
    assert settings.ANTHROPIC_API_KEY in ("", "mock-anthropic-key"), \
        "ANTHROPIC_API_KEY is set to a real value — is_mock_mode will be False in CI"
    assert settings.GEMINI_API_KEY    in ("", "mock-gemini-key"),    \
        "GEMINI_API_KEY is set to a real value — is_mock_mode will be False in CI"

    assert settings.is_mock_mode is True, (
        "settings.is_mock_mode should be True when all keys are at their placeholder defaults"
    )


def test_is_mock_mode_false_when_openai_key_set():
    """
    settings.is_mock_mode must return False as soon as any real key is present.
    """
    from backend.app.core.config import Settings

    patched = Settings(
        OPENAI_API_KEY="sk-real-key-example",
        ANTHROPIC_API_KEY="mock-anthropic-key",
        GEMINI_API_KEY="mock-gemini-key",
    )
    assert patched.is_mock_mode is False


def test_is_mock_mode_false_when_anthropic_key_set():
    from backend.app.core.config import Settings

    patched = Settings(
        OPENAI_API_KEY="mock-openai-key",
        ANTHROPIC_API_KEY="sk-ant-real-key",
        GEMINI_API_KEY="mock-gemini-key",
    )
    assert patched.is_mock_mode is False


def test_is_mock_mode_false_when_gemini_key_set():
    from backend.app.core.config import Settings

    patched = Settings(
        OPENAI_API_KEY="mock-openai-key",
        ANTHROPIC_API_KEY="mock-anthropic-key",
        GEMINI_API_KEY="AIzaSy-real-key",
    )
    assert patched.is_mock_mode is False


# ---------------------------------------------------------------------------
# 2. Key propagation via llm_client
# ---------------------------------------------------------------------------

def test_llm_client_does_not_set_env_for_mock_keys():
    """
    When all keys are placeholders, llm_client must NOT write them into
    os.environ (to avoid LiteLLM attempting to authenticate with junk values).
    """
    # Ensure the placeholder env vars are not already set as real keys
    env_backup = {k: os.environ.pop(k, None)
                  for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY")}
    try:
        import backend.app.utils.llm_client  # noqa: F401  (import for side-effect)
        importlib.reload(backend.app.utils.llm_client)

        # None of the placeholder keys should be written into the environment
        assert os.environ.get("OPENAI_API_KEY")    != "mock-openai-key"
        assert os.environ.get("ANTHROPIC_API_KEY") != "mock-anthropic-key"
        assert os.environ.get("GEMINI_API_KEY")    != "mock-gemini-key"
    finally:
        # Restore original env
        for k, v in env_backup.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_llm_client_sets_env_when_real_openai_key_given():
    """
    When a real OpenAI key is injected into settings, llm_client.push_keys()
    writes it to os.environ so LiteLLM (and the OpenAI SDK) can pick it up.
    """
    import litellm
    import backend.app.utils.llm_client as llm_client_module
    from backend.app.core.config import settings

    fake_key = "sk-unittest-fake-key-1234"

    env_backup = os.environ.pop("OPENAI_API_KEY", None)
    orig_litellm_key = getattr(litellm, "openai_key", None)

    try:
        with patch.object(settings, "OPENAI_API_KEY", fake_key):
            llm_client_module._push_keys()

            # Key must now be available to the LiteLLM global
            assert litellm.openai_key == fake_key
            # And to the process environment
            assert os.environ.get("OPENAI_API_KEY") == fake_key
    finally:
        # Restore
        litellm.openai_key = orig_litellm_key
        if env_backup is not None:
            os.environ["OPENAI_API_KEY"] = env_backup
        else:
            os.environ.pop("OPENAI_API_KEY", None)
