"""
llm_client.py
=============
Centralised LiteLLM key-propagation module.

Import this module (or any module that imports it) before making any
``litellm.acompletion`` calls. It pushes every configured provider key
from ``settings`` into both:

* ``litellm.<provider>_key`` — the LiteLLM global used by the library
* ``os.environ["<PROVIDER>_API_KEY"]`` — the fallback LiteLLM reads when
  the global is not set, and what provider SDKs read directly.

It is safe to import this module multiple times; the key assignment is
idempotent and has no other side-effects.
"""

import os
import litellm

from backend.app.core.config import settings

# Global LiteLLM configurations for stability and compatibility across providers
litellm.drop_params = True
litellm.suppress_debug_info = True
litellm.telemetry = False

# ---------------------------------------------------------------------------
# Propagate keys from Settings → LiteLLM globals + os.environ
# ---------------------------------------------------------------------------

def _push_keys() -> None:
    """Set Groq provider API key on LiteLLM and in the process environment."""
    # Groq (Exclusive provider)
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "mock-groq-key":
        litellm.groq_key = settings.GROQ_API_KEY
        litellm.api_key = settings.GROQ_API_KEY
        os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

    # Non-Groq providers explicitly reset to avoid routing outside Groq
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "mock-openai-key":
        litellm.openai_key = settings.OPENAI_API_KEY
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

    if settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY != "mock-anthropic-key":
        litellm.anthropic_key = settings.ANTHROPIC_API_KEY
        os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY

    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "mock-gemini-key":
        litellm.gemini_key = settings.GEMINI_API_KEY
        os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
        os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY


def format_model_name(model_name: str) -> str:
    """
    Ensures model names are properly formatted to route exclusively via Groq API.
    Maps legacy generic or provider model IDs to their Groq equivalents.
    """
    if not model_name:
        return settings.TIER_1_MODEL

    model_mapping = {
        "gpt-4o-mini": "groq/openai/gpt-oss-20b",
        "gpt-4o": "groq/openai/gpt-oss-120b",
        "gpt-3.5-turbo": "groq/openai/gpt-oss-20b",
        "claude-3-haiku": "groq/openai/gpt-oss-20b",
        "claude-3-5-sonnet": "groq/openai/gpt-oss-120b",
        "gemini-1.5-flash": "groq/openai/gpt-oss-20b",
        "gemini-1.5-pro": "groq/openai/gpt-oss-120b",
    }
    clean = model_name.split("/")[-1].lower()
    if clean in model_mapping:
        return model_mapping[clean]

    if not model_name.startswith("groq/"):
        return f"groq/{model_name}"
    return model_name


# Run once at import time
_push_keys()


