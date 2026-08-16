import pytest
import asyncio
from sqlalchemy import select
from backend.app.core.confidence import ConfidenceEvaluator
from backend.app.core.router_engine import router_engine
from backend.app.db.session import init_db, SessionLocal
from backend.app.db.models import RoutingPolicy

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

async def test_syntactic_evaluation():
    # Valid JSON
    valid_json = '{"name": "test", "value": 42}'
    assert ConfidenceEvaluator.evaluate_syntactic(valid_json, "json") >= 0.9

    # Malformed JSON
    malformed_json = '{"name": "test", "value": 42'
    assert ConfidenceEvaluator.evaluate_syntactic(malformed_json, "json") <= 0.2

    # Valid Python Code
    valid_python = "def solution(x):\n    return x * 2"
    assert ConfidenceEvaluator.evaluate_syntactic(valid_python, "python") == 1.0

    # Invalid Python Code
    invalid_python = "def solution(x)\n    return x * 2"
    assert ConfidenceEvaluator.evaluate_syntactic(invalid_python, "python") <= 0.2

async def test_semantic_hedging():
    confident_text = "The quick brown fox jumps over the lazy dog. The transaction has completed successfully."
    assert ConfidenceEvaluator.evaluate_semantic_hedging(confident_text) == 1.0

    hedged_text = "I think this is correct, but I'm not sure. Please verify."
    assert ConfidenceEvaluator.evaluate_semantic_hedging(hedged_text) <= 0.7

async def test_complexity_classification():
    # Simple query should trigger Tier 1
    assert router_engine.classify_complexity("Hello, what is the time?") == 1

    # RAG lookup query should trigger Tier 2
    assert router_engine.classify_complexity("What is the token pricing of the gateway?") == 2

    # Coding query should trigger Tier 3
    assert router_engine.classify_complexity("write a python script to reverse a linked list") == 3

    # Extreme verification query should trigger Tier 4
    assert router_engine.classify_complexity("Execute a high stakes security audit consensus verification check") == 4

async def test_routing_cascade_mock():
    # Setup test DB tables (Sync initialization)
    init_db()
    
    with SessionLocal() as session:
        # A query with JSON keyword will trigger malformed response in Tier 1 mock
        # which should escalate to Tier 3 (Frontier) to get a clean JSON response.
        result = await router_engine.route(
            prompt="Generate a configuration JSON",
            domain="coding",
            expected_format="json",
            db=session
        )
        
        # Verify routing completed
        assert result["text"] is not None
        # Verify it escalated past Tier 1 (since Tier 1 mock outputs malformed JSON)
        assert result["final_tier"] >= 2
        # Verify the tracking steps exist
        assert len(result["usage"]["routing_path"]) >= 1
        # Verify total cost calculation was tracked
        assert result["usage"]["total_cost_usd"] > 0.0

async def test_agent_tiers_execution():
    """Verify each tier can execute, adheres to common interface, and returns correct fields."""
    for tier, agent in router_engine.agents.items():
        res = await agent.execute(prompt="Test task execution status")
        assert "text" in res
        assert "model_name" in res
        assert "tokens_input" in res
        assert "tokens_output" in res
        assert "cost" in res
        assert "latency_ms" in res
        assert res["tier"] == tier
        assert isinstance(res["text"], str)
        assert res["cost"] >= 0.0
        assert res["latency_ms"] >= 0

from unittest.mock import patch

async def test_failed_agents_graceful_handling():
    """Verify that if an agent raises an exception, the router recovers, logs the failure, and escalates."""
    # Patch Tier 1 execute method to raise an Exception
    with patch.object(router_engine.agents[1], 'execute', side_effect=Exception("Connection timed out")):
        result = await router_engine.route(
            prompt="Simple greeting",
            domain="general"
        )
        
        # Verify it still returned a valid final response (recovering and executing Tier 2/etc.)
        assert result["text"] is not None
        assert result["final_tier"] >= 2
        
        # Verify the execution steps logged the failure
        steps = result["usage"]["routing_path"]
        assert len(steps) >= 2
        assert steps[0]["tier"] == 1
        assert "FAILED" in steps[0]["model_name"]
        assert steps[0]["confidence_score"] == 0.0
        assert steps[0]["cost"] == 0.0

async def test_final_response_schema_and_tracking():
    """Verify that cost, latency, and full execution paths are correctly tracked and formatted in the response."""
    result = await router_engine.route(
        prompt="Explain token pricing metrics",
        domain="general"
    )
    
    # Verify top-level return dictionary format
    assert "text" in result
    assert "final_tier" in result
    assert "threshold_used" in result
    assert "usage" in result
    
    usage = result["usage"]
    assert "total_cost_usd" in usage
    assert "total_latency_ms" in usage
    assert "routing_path" in usage
    
    # Verify values are correctly recorded
    assert usage["total_cost_usd"] > 0.0
    assert usage["total_latency_ms"] >= 0
    assert len(usage["routing_path"]) >= 1
    
    # Verify step properties
    for step in usage["routing_path"]:
        assert "tier" in step
        assert "model_name" in step
        assert "confidence_score" in step
        assert "tokens_input" in step
        assert "tokens_output" in step
        assert "cost" in step
        assert "latency_ms" in step

async def test_simple_high_confidence_query():
    """Scenario 1: Simple high-confidence query is accepted at a lower tier (Tier 1)."""
    with patch.object(router_engine.agents[1], 'execute', return_value={
        "text": "The capital of Spain is Madrid. The transaction has completed successfully.",
        "model_name": "gpt-4o-mini (Simulated)",
        "tokens_input": 10,
        "tokens_output": 10,
        "cost": 0.0001,
        "latency_ms": 100,
        "tier": 1
    }):
        result = await router_engine.route(
            prompt="What is the capital of Spain?",
            domain="general"
        )
        assert result["final_tier"] == 1
        assert len(result["usage"]["routing_path"]) == 1

async def test_invalid_json_escalated():
    """Scenario 2: Invalid JSON formatting fails syntactic checks and gets escalated."""
    result = await router_engine.route(
        prompt="Output configuration JSON",
        domain="general", # general domain so it starts at Tier 1
        expected_format="json"
    )
    assert result["final_tier"] >= 2
    steps = result["usage"]["routing_path"]
    assert steps[0]["confidence_score"] <= 0.2

async def test_hedging_response_escalated():
    """Scenario 3: Uncertain or hedging responses drop confidence below threshold and get escalated."""
    with patch.object(router_engine.agents[1], 'execute', return_value={
        "text": "I think the capital of France is probably Paris. I am not fully certain, so please verify as I cannot guarantee this.",
        "model_name": "gpt-4o-mini (Simulated)",
        "tokens_input": 10,
        "tokens_output": 10,
        "cost": 0.0001,
        "latency_ms": 100,
        "tier": 1
    }):
        result = await router_engine.route(
            prompt="What is the capital of France?",
            domain="general"
        )
        assert result["final_tier"] >= 2
        steps = result["usage"]["routing_path"]
        assert steps[0]["confidence_score"] <= 0.50

async def test_high_confidence_no_unnecessary_escalation():
    """Scenario 4: High-confidence response has no unnecessary escalation."""
    with patch.object(router_engine.agents[1], 'execute', return_value={
        "text": "The transaction has completed successfully. Here is the verified answer.",
        "model_name": "gpt-4o-mini (Simulated)",
        "tokens_input": 10,
        "tokens_output": 10,
        "cost": 0.0001,
        "latency_ms": 100,
        "tier": 1
    }):
        result = await router_engine.route(
            prompt="Verify transaction status",
            domain="general"
        )
        assert result["final_tier"] == 1
        assert len(result["usage"]["routing_path"]) == 1

async def test_policy_threshold_changes_routing():
    """Scenario 5: Policy threshold changes affect routing and escalation logic correctly."""
    init_db()
    with SessionLocal() as db:
        # Get or create the policy
        policy_res = db.execute(select(RoutingPolicy).where(RoutingPolicy.domain == "general"))
        policy = policy_res.scalars().first()
        if not policy:
            policy = RoutingPolicy(domain="general", min_confidence_threshold=0.95)
            db.add(policy)
        else:
            policy.min_confidence_threshold = 0.95
        db.commit()
        
        # Mock Tier 1 to return a good answer (with one hedging keyword "probably", yielding confidence ~0.82)
        with patch.object(router_engine.agents[1], 'execute', return_value={
            "text": "The answer is probably correct.",
            "model_name": "gpt-4o-mini (Simulated)",
            "tokens_input": 10,
            "tokens_output": 10,
            "cost": 0.0001,
            "latency_ms": 100,
            "tier": 1
        }):
            result = await router_engine.route(
                prompt="Check answer validity",
                domain="general",
                db=db
            )
            # Should escalate past Tier 1 because 0.82 < 0.95
            assert result["final_tier"] >= 2
            
        # Restore threshold back to 0.65
        policy.min_confidence_threshold = 0.65
        db.commit()

async def test_cost_savings_in_response():
    """Verify that estimated_frontier_cost_usd and cost_savings_usd are returned and non-negative."""
    with patch.object(router_engine.agents[1], 'execute', return_value={
        "text": "The capital of Germany is Berlin.",
        "model_name": "gpt-4o-mini (Simulated)",
        "tokens_input": 20,
        "tokens_output": 20,
        "cost": 0.000005,
        "latency_ms": 100,
        "tier": 1
    }):
        result = await router_engine.route(
            prompt="What is the capital of Germany?",
            domain="general"
        )

    usage = result["usage"]
    assert "estimated_frontier_cost_usd" in usage, "estimated_frontier_cost_usd missing from usage"
    assert "cost_savings_usd" in usage, "cost_savings_usd missing from usage"
    assert usage["estimated_frontier_cost_usd"] >= 0.0
    assert usage["cost_savings_usd"] >= 0.0
    # Actual cost should be <= frontier cost (we saved something by using a cheap tier)
    assert usage["total_cost_usd"] <= usage["estimated_frontier_cost_usd"] + 1e-10

async def test_budget_limit_stops_escalation():
    """Verify that budget_limit_usd prevents escalation once cost is reached."""
    # Tier 1 mock returns malformed JSON (expected_format=json) so it would normally escalate.
    # But set a tiny budget that Tier 1 already exceeds, forcing the router to stop.
    with patch.object(router_engine.agents[1], 'execute', return_value={
        "text": '{ "broken": "json"',    # malformed — would normally trigger escalation
        "model_name": "gpt-4o-mini (Simulated)",
        "tokens_input": 10,
        "tokens_output": 10,
        "cost": 0.01,   # cost > budget_limit, so no escalation should happen
        "latency_ms": 100,
        "tier": 1
    }):
        result = await router_engine.route(
            prompt="Give me a config JSON",
            domain="general",
            expected_format="json",
            budget_limit_usd=0.001   # much less than the 0.01 Tier 1 cost
        )

    usage = result["usage"]
    assert usage["budget_exceeded"] is True, "budget_exceeded flag should be True"
    # With budget enforced at Tier 1, should NOT escalate past Tier 1
    assert result["final_tier"] == 1, "Router should stop at Tier 1 when budget is hit"
