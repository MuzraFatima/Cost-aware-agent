import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.router_engine import router_engine
from backend.app.utils.cost_tracker import (
    calculate_token_cost,
    estimate_tokens,
    estimate_pre_request_cost,
    calculate_budget_status
)

client = TestClient(app)

def test_pre_request_cost_estimation():
    """Verify prompt token estimation and pre-request model cost calculations."""
    prompt = "Write a Python script to sort a list using quicksort algorithm."
    tokens = estimate_tokens(prompt)
    assert tokens > 0
    
    # Test cheap model estimate
    cost_cheap = estimate_pre_request_cost("groq/openai/gpt-oss-20b", prompt, expected_output_tokens=300)
    assert cost_cheap > 0.0
    
    # Test frontier model estimate
    cost_frontier = estimate_pre_request_cost("groq/openai/gpt-oss-120b", prompt, expected_output_tokens=300)
    assert cost_frontier > cost_cheap

    # Test consensus loop multi-call estimate
    cost_consensus = estimate_pre_request_cost("Consensus Loop", prompt, expected_output_tokens=300)
    assert cost_consensus > cost_frontier

def test_budget_status_calculation():
    """Verify calculation of remaining daily/monthly budgets and 0-100 pressure score."""
    status = calculate_budget_status(daily_limit=10.0, monthly_limit=100.0)
    assert status["daily_budget_usd"] == 10.0
    assert status["monthly_budget_usd"] == 100.0
    assert status["remaining_daily_budget_usd"] <= 10.0
    assert status["remaining_monthly_budget_usd"] <= 100.0
    assert 0 <= status["budget_pressure_score"] <= 100

@pytest.mark.asyncio
async def test_router_normal_routing_low_pressure():
    """Verify normal task classification and tier selection when budget pressure is low."""
    res = await router_engine.route("What is Python?")
    assert res["task_type"] == "general"
    assert res["complexity_score"] <= 3
    assert res["final_tier"] <= 2
    assert "routing_reason" in res
    assert "Budget pressure:" in res["routing_reason"]
    assert "usage" in res
    assert "pre_request_estimated_cost_usd" in res["usage"]

@pytest.mark.asyncio
async def test_router_per_request_budget_limit_downgrade():
    """
    Verify automatic tier downgrade when per-request budget_limit_usd is set below candidate cost.
    """
    # Prompt would normally target Tier 3/4 due to high complexity
    complex_prompt = "Design a complex multi-agent reinforcement learning system with distributed optimization."
    
    # Budget cap smaller than Tier 3 estimate ($0.000542) but sufficient for Tier 1 ($0.000082)
    tight_budget = 0.0002
    res = await router_engine.route(complex_prompt, budget_limit_usd=tight_budget)
    
    assert res["final_tier"] < 4
    assert "Downgraded target Tier" in res["routing_reason"] or "exceeds request budget limit" in res["routing_reason"]

def test_analytics_summary_and_budget_endpoints():
    """Verify /api/v1/analytics/summary and /api/v1/analytics/budget API endpoints."""
    # Test GET summary
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "daily_budget_usd" in data
    assert "monthly_budget_usd" in data
    assert "budget_pressure_score" in data
    assert "remaining_daily_budget_usd" in data
    
    # Test POST budget limits update
    post_res = client.post(
        "/api/v1/analytics/budget",
        json={"daily_budget_usd": 15.0, "monthly_budget_usd": 150.0}
    )
    assert post_res.status_code == 200
    updated_data = post_res.json()
    assert updated_data["daily_budget_usd"] == 15.0
    assert updated_data["monthly_budget_usd"] == 150.0
