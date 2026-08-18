"""
test_e2e_live_path.py
=====================
End-to-end verification of the REAL LLM integration path.

Strategy
--------
Because no real API key is required to be present in CI, we verify the live
code path by:
  1. Patching ``settings.is_mock_mode`` → False   (bypass the mock guard)
  2. Patching ``litellm.acompletion``             (inject a realistic response
     object without hitting the network)

This exercises EVERY line of the live path:
  • Agent builds messages and calls ``litellm.acompletion``
  • Response text, token counts, and cost are extracted
  • ``model_name`` has no ``(Simulated)`` suffix
  • RouterEngine runs confidence scoring, escalation logic, cost tracking,
    latency measurement, and DB persistence — all with the real-path response

A separate ``test_live_api_*`` test actually calls the real provider when a
real API key is available; it is automatically skipped otherwise.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.app.core.config import settings
from backend.app.db.session import init_db, SessionLocal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio

# True when settings has at least one real provider key (from env var OR .env file).
# Controls whether test_live_api_cheap_agent_real_call runs or is skipped.
_REAL_KEY_PRESENT = not settings.is_mock_mode


def _make_litellm_response(
    text: str,
    prompt_tokens: int = 12,
    completion_tokens: int = 20,
    model: str = "gpt-4o-mini",
) -> SimpleNamespace:
    """
    Build a lightweight object that mirrors the fields agents read from a
    real ``litellm.acompletion`` response — without any network call.
    """
    return SimpleNamespace(
        id="chatcmpl-unittest",
        model=model,
        choices=[
            SimpleNamespace(
                index=0,
                message=SimpleNamespace(
                    role="assistant",
                    content=text,
                ),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


# ---------------------------------------------------------------------------
# 1. CheapAgent live path
# ---------------------------------------------------------------------------

async def test_cheap_agent_live_path_returns_real_response():
    """
    CheapAgent must use the litellm response text directly (not mock) and
    return a model_name without '(Simulated)' when is_mock_mode is False.
    """
    from backend.app.agents.cheap_agent import CheapAgent
    from backend.app.core.config import settings

    agent = CheapAgent()
    fake_response = _make_litellm_response(
        text="The capital of France is Paris.",
        prompt_tokens=8,
        completion_tokens=9,
    )

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_response)):
            result = await agent.execute(prompt="What is the capital of France?")

    assert result["text"] == "The capital of France is Paris."
    assert "(Simulated)" not in result["model_name"], \
        f"Real path should not produce a simulated label; got: {result['model_name']}"
    assert result["tokens_input"] == 8
    assert result["tokens_output"] == 9
    assert result["cost"] > 0.0
    assert result["latency_ms"] >= 0
    assert result["tier"] == 1


async def test_cheap_agent_live_path_fallback_on_error():
    """
    If litellm.acompletion raises any exception in the live path, the agent
    must fall back to the mock path without propagating the error.
    """
    from backend.app.agents.cheap_agent import CheapAgent
    from backend.app.core.config import settings

    agent = CheapAgent()

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=AsyncMock(side_effect=Exception("Connection refused"))):
            result = await agent.execute(prompt="What is the capital of Germany?")

    # Must still return a valid result (the mock fallback)
    assert isinstance(result["text"], str) and len(result["text"]) > 0
    assert "(Simulated)" in result["model_name"]
    assert result["tier"] == 1


# ---------------------------------------------------------------------------
# 2. FrontierAgent live path
# ---------------------------------------------------------------------------

async def test_frontier_agent_live_path_returns_real_response():
    """
    FrontierAgent live path must return the raw LLM text with proper fields.
    """
    from backend.app.agents.frontier_agent import FrontierAgent
    from backend.app.core.config import settings

    agent = FrontierAgent()
    fake_response = _make_litellm_response(
        text="Python is a high-level programming language emphasising readability.",
        prompt_tokens=15,
        completion_tokens=12,
        model="gpt-4o",
    )

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_response)):
            result = await agent.execute(prompt="What is Python?")

    assert "Python" in result["text"]
    assert "(Simulated)" not in result["model_name"]
    assert result["tokens_input"] == 15
    assert result["tokens_output"] == 12
    assert result["cost"] > 0.0
    assert result["tier"] == 3


# ---------------------------------------------------------------------------
# 3. RAGAgent live path
# ---------------------------------------------------------------------------

async def test_rag_agent_live_path_uses_augmented_prompt():
    """
    RAGAgent must pass an augmented (context + question) prompt to LiteLLM,
    not just the raw question.
    """
    from backend.app.agents.rag_agent import RAGAgent
    from backend.app.core.config import settings

    agent = RAGAgent()
    captured_calls = []

    async def capture_completion(**kwargs):
        captured_calls.append(kwargs)
        return _make_litellm_response(
            text="CAAR reduces costs by routing to cheaper models.",
            prompt_tokens=30,
            completion_tokens=10,
        )

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=capture_completion):
            result = await agent.execute(prompt="Explain the token pricing strategy")

    assert len(captured_calls) == 1
    # The prompt sent to LiteLLM must contain the context prefix
    sent_messages = captured_calls[0]["messages"]
    combined_content = " ".join(m["content"] for m in sent_messages)
    assert "Context:" in combined_content, \
        "RAGAgent must prepend retrieved context to the LiteLLM messages"
    assert result["text"] == "CAAR reduces costs by routing to cheaper models."
    assert "(RAG)" in result["model_name"]
    assert result["tier"] == 2


# ---------------------------------------------------------------------------
# 4. ConsensusAgent live path
# ---------------------------------------------------------------------------

async def test_consensus_agent_live_path_makes_three_calls():
    """
    ConsensusAgent must fire exactly 3 LiteLLM calls:
      Call 1 — cheap model candidate A  (concurrent)
      Call 2 — frontier model candidate B  (concurrent)
      Call 3 — frontier model synthesis / critic
    Costs are aggregated correctly across all three.
    """
    from backend.app.agents.consensus_agent import ConsensusAgent
    from backend.app.core.config import settings

    agent = ConsensusAgent()
    call_log = []

    async def three_way_completion(**kwargs):
        n = len(call_log)
        call_log.append(kwargs)
        texts = [
            "Candidate A: The answer is 42.",
            "Candidate B: The answer is definitely 42.",
            "Final verified answer: The answer is 42, confirmed by both candidates.",
        ]
        return _make_litellm_response(
            text=texts[n] if n < 3 else "Extra call",
            prompt_tokens=20,
            completion_tokens=15,
        )

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=three_way_completion):
            result = await agent.execute(prompt="What is the answer to life?")

    assert len(call_log) == 3, \
        f"ConsensusAgent must make exactly 3 LiteLLM calls; got {len(call_log)}"
    assert "verified" in result["text"].lower() or "confirmed" in result["text"].lower()
    # Aggregated tokens: 3 calls × 20 in + 15 out = 105 tokens total
    assert result["tokens_input"] == 60   # 3 × 20
    assert result["tokens_output"] == 45  # 3 × 15
    assert result["cost"] > 0.0
    assert result["tier"] == 4


# ---------------------------------------------------------------------------
# 5. End-to-end router pipeline with live-path agents
# ---------------------------------------------------------------------------

async def test_router_e2e_live_path_pipeline():
    """
    Full pipeline with live agents:
      - Mock is_mock_mode = False for all agents
      - Tier 1 returns a high-confidence, non-hedging response
      - Router must accept it at Tier 1 without escalation
      - Cost, latency, confidence score, and routing path are all recorded
      - DB log entry is created with correct fields
    """
    from backend.app.core.router_engine import RouterEngine
    from backend.app.core.config import settings

    init_db()
    engine = RouterEngine()

    fake_response = _make_litellm_response(
        text="Berlin is the capital of Germany. The answer has been fully verified.",
        prompt_tokens=10,
        completion_tokens=14,
    )

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=AsyncMock(return_value=fake_response)):
            with SessionLocal() as db:
                result = await engine.route(
                    prompt="What is the capital of Germany?",
                    domain="general",
                    db=db,
                )

    # Response shape
    assert result["text"] == "Berlin is the capital of Germany. The answer has been fully verified."
    assert result["final_tier"] == 1, \
        "High-confidence answer must be accepted at Tier 1 without escalation"
    assert result["threshold_used"] > 0.0

    # Routing path
    path = result["usage"]["routing_path"]
    assert len(path) == 1, "Only one tier should be traversed"
    step = path[0]
    assert step["tier"] == 1
    assert "(Simulated)" not in step["model_name"]
    assert step["confidence_score"] >= 0.65  # above general threshold
    assert step["tokens_input"] == 10
    assert step["tokens_output"] == 14
    assert step["cost"] > 0.0
    assert step["latency_ms"] >= 0

    # Cost tracking
    usage = result["usage"]
    assert usage["total_cost_usd"] > 0.0
    assert usage["estimated_frontier_cost_usd"] >= 0.0
    assert usage["cost_savings_usd"] >= 0.0
    assert usage["total_latency_ms"] >= 0

    # DB log
    assert result["id"] is not None, "A routing_log DB row must have been created"


async def test_router_e2e_live_path_escalates_on_low_confidence():
    """
    When Tier 1 returns a hedging response in the live path, the router must
    escalate to Tier 2.
    """
    from backend.app.core.router_engine import RouterEngine
    from backend.app.core.config import settings

    engine = RouterEngine()

    # Tier 1 response: hedging → low confidence → escalation
    hedging_response = _make_litellm_response(
        text="I'm not sure, but it might be Paris. Please verify this answer.",
        prompt_tokens=10,
        completion_tokens=12,
    )
    # Tier 2 response: confident
    confident_response = _make_litellm_response(
        text="The capital of France is Paris.",
        prompt_tokens=30,
        completion_tokens=8,
    )

    call_count = 0

    async def tiered_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return hedging_response if call_count == 1 else confident_response

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=tiered_completion):
            result = await engine.route(
                prompt="What is the capital of France?",
                domain="general",
            )

    assert result["final_tier"] >= 2, "Router must escalate past Tier 1 on hedging response"
    path = result["usage"]["routing_path"]
    assert len(path) >= 2
    assert path[0]["confidence_score"] <= 0.70  # hedging penalised
    assert path[0]["tier"] == 1
    # Costs are accumulated
    assert result["usage"]["total_cost_usd"] > 0.0


async def test_router_e2e_live_path_json_escalation():
    """
    When Tier 1 returns malformed JSON in the live path (syntactic failure),
    the router must escalate to a higher tier that can produce valid JSON.
    """
    from backend.app.core.router_engine import RouterEngine
    from backend.app.core.config import settings

    engine = RouterEngine()

    malformed_json_response = _make_litellm_response(
        text='{ "status": "broken"',   # intentionally malformed
        prompt_tokens=10,
        completion_tokens=6,
    )
    valid_json_response = _make_litellm_response(
        text='{"status": "success", "data": {"key": "value"}}',
        prompt_tokens=25,
        completion_tokens=12,
    )

    call_count = 0

    async def json_tiered_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        return malformed_json_response if call_count == 1 else valid_json_response

    with patch.object(settings.__class__, "is_mock_mode", new_callable=lambda: property(lambda s: False)):
        with patch("litellm.acompletion", new=json_tiered_completion):
            result = await engine.route(
                prompt="Generate a configuration JSON",
                domain="coding",
                expected_format="json",
            )

    assert result["final_tier"] >= 2
    path = result["usage"]["routing_path"]
    assert path[0]["confidence_score"] <= 0.2, \
        "Malformed JSON must yield a very low syntactic confidence score"


# ---------------------------------------------------------------------------
# 6. Live API tests (auto-skipped when no real key is configured)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _REAL_KEY_PRESENT,
    reason="No real LLM API key configured in environment or .env — skipping live API test"
)
async def test_live_api_cheap_agent_real_call():
    """
    When a real API key is present, this test fires an actual LiteLLM
    call and verifies the full response pipeline.

    Skipped automatically in CI / sandbox environments without a real key.
    """
    from backend.app.agents.cheap_agent import CheapAgent
    from backend.app.core.config import settings

    assert not settings.is_mock_mode, \
        "is_mock_mode must be False when a real key is configured"

    agent = CheapAgent()
    result = await agent.execute(prompt="Reply with exactly the word: PONG")

    assert isinstance(result["text"], str) and len(result["text"]) > 0
    assert "(Simulated)" not in result["model_name"], \
        "Live call must not have (Simulated) in model_name"
    assert result["tokens_input"] > 0
    assert result["tokens_output"] > 0
    assert result["cost"] >= 0.0
    assert result["latency_ms"] >= 0
    assert result["tier"] == 1


@pytest.mark.skipif(
    not _REAL_KEY_PRESENT,
    reason="No real LLM API key configured in environment or .env — skipping live API test"
)
async def test_live_api_router_engine_real_call():
    """
    When a real API key is present, verify that RouterEngine routes through real LLM
    and returns actual LLM response with proper tracking.
    """
    from backend.app.core.router_engine import RouterEngine
    from backend.app.core.config import settings

    assert not settings.is_mock_mode

    engine = RouterEngine()
    result = await engine.route(
        prompt="Say 'Hello' in one word.",
        domain="general"
    )

    assert isinstance(result["text"], str) and len(result["text"].strip()) > 0
    assert result["final_tier"] >= 1
    assert result["usage"]["total_cost_usd"] >= 0.0
    assert result["usage"]["total_latency_ms"] >= 0
    assert len(result["usage"]["routing_path"]) >= 1
    # First step executed must have been a real model, not simulated
    assert "(Simulated)" not in result["usage"]["routing_path"][0]["model_name"]

