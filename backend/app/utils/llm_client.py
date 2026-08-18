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
    """Set provider API keys on LiteLLM and in the process environment."""

    # OpenAI
    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "mock-openai-key":
        litellm.openai_key = settings.OPENAI_API_KEY
        litellm.api_key = settings.OPENAI_API_KEY
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

    # Anthropic
    if settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY != "mock-anthropic-key":
        litellm.anthropic_key = settings.ANTHROPIC_API_KEY
        os.environ["ANTHROPIC_API_KEY"] = settings.ANTHROPIC_API_KEY

    # Google / Gemini
    if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "mock-gemini-key":
        litellm.gemini_key = settings.GEMINI_API_KEY
        os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
        os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY


# Run once at import time
_push_keys()

