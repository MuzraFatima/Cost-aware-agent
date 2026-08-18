"""
test_benchmark.py
=================
Comprehensive unit and integration tests for the Evaluation & Benchmarking module.

Verifies:
  1. Benchmark dataset structure and coverage across all 5 required domains:
     - Factual questions
     - Coding
     - Mathematics
     - JSON / structured output
     - Reasoning
  2. Validator logic across all validation types (json, python_code, contains)
  3. Metric aggregation and calculation accuracy (accuracy, cost, latency, confidence, escalation, savings)
  4. End-to-end execution of Tier 1 only, Highest-tier only, and CAAR strategies
  5. Markdown comparison report formatting and integrity
"""

import pytest
import json
from typing import List

from backend.app.evaluation.dataset import BenchmarkItem, BENCHMARK_DATASET
from backend.app.evaluation.evaluator import (
    BenchmarkEvaluator,
    BenchmarkReport,
    StrategyMetrics,
    QueryResult,
    validate_item_response,
    format_benchmark_markdown_report,
)


# ---------------------------------------------------------------------------
# 1. Dataset Integrity Tests
# ---------------------------------------------------------------------------

def test_benchmark_dataset_coverage():
    """Verify that the benchmark dataset contains all 5 required categories."""
    categories = {item.category for item in BENCHMARK_DATASET}
    required_categories = {"factual", "coding", "mathematics", "json", "reasoning"}

    assert required_categories.issubset(categories), (
        f"Benchmark dataset missing categories. Expected {required_categories}, found {categories}"
    )
    assert len(BENCHMARK_DATASET) >= 15, "Benchmark dataset should contain at least 15 items"


def test_benchmark_dataset_item_fields():
    """Verify that every BenchmarkItem has non-empty required attributes."""
    for item in BENCHMARK_DATASET:
        assert item.id, "Item missing ID"
        assert item.category, f"Item {item.id} missing category"
        assert item.prompt and len(item.prompt.strip()) > 0, f"Item {item.id} missing prompt"
        assert item.domain in ("general", "coding", "math", "creative"), f"Item {item.id} invalid domain: {item.domain}"
        assert item.validation_type in ("contains", "json_schema", "python_code"), f"Item {item.id} invalid validation_type"


# ---------------------------------------------------------------------------
# 2. Response Validator Tests
# ---------------------------------------------------------------------------

def test_validator_json_success():
    """Test validation of valid structured JSON output."""
    item = BenchmarkItem(
        id="test_json",
        category="json",
        prompt="Generate JSON",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["status"]
    )
    valid_json = '{"status": "success", "data": {"user_id": 42}}'
    is_valid, msg = validate_item_response(item, valid_json)
    assert is_valid is True


def test_validator_json_malformed_failure():
    """Test validation fails properly on malformed JSON."""
    item = BenchmarkItem(
        id="test_json",
        category="json",
        prompt="Generate JSON",
        expected_format="json",
        validation_type="json_schema"
    )
    malformed_json = '{"status": "incomplete", "data": '  # missing closing brace
    is_valid, msg = validate_item_response(item, malformed_json)
    assert is_valid is False
    assert "Failed JSON parsing" in msg or "Malformed" in msg


def test_validator_python_code_success():
    """Test validation of valid Python code."""
    item = BenchmarkItem(
        id="test_code",
        category="coding",
        prompt="Write a reverse function",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "return"]
    )
    valid_code = "```python\ndef reverse_list(arr):\n    return arr[::-1]\n```"
    is_valid, msg = validate_item_response(item, valid_code)
    assert is_valid is True


def test_validator_python_code_syntax_error():
    """Test validation fails on invalid Python syntax."""
    item = BenchmarkItem(
        id="test_code",
        category="coding",
        prompt="Write a reverse function",
        expected_format="python",
        validation_type="python_code"
    )
    invalid_code = "def broken_func(x\n    return x"  # missing closing paren & colon
    is_valid, msg = validate_item_response(item, invalid_code)
    assert is_valid is False
    assert "SyntaxError" in msg


def test_validator_contains_keywords():
    """Test keyword presence validation."""
    item = BenchmarkItem(
        id="test_fact",
        category="factual",
        prompt="Capital of France",
        validation_type="contains",
        expected_keywords=["Paris"]
    )
    assert validate_item_response(item, "The capital of France is Paris.")[0] is True
    assert validate_item_response(item, "The capital is London.")[0] is False


# ---------------------------------------------------------------------------
# 3. Benchmark Execution & Comparison Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_subset_execution():
    """
    Run a mini-benchmark on a subset of 5 items (1 per category) to verify
    Tier 1, Highest-Tier, and CAAR execution and metrics aggregation.
    """
    subset = [
        BENCHMARK_DATASET[0],  # factual
        BENCHMARK_DATASET[4],  # coding
        BENCHMARK_DATASET[8],  # math
        BENCHMARK_DATASET[12], # json
        BENCHMARK_DATASET[16], # reasoning
    ]

    evaluator = BenchmarkEvaluator(dataset=subset)
    report = await evaluator.run_full_benchmark()

    # 1. Report structure check
    assert report.total_items == 5
    assert len(report.strategies) == 3
    assert "tier_1_only" in report.strategies
    assert "highest_tier_only" in report.strategies
    assert "cost_aware_router" in report.strategies

    t1 = report.strategies["tier_1_only"]
    ht = report.strategies["highest_tier_only"]
    caar = report.strategies["cost_aware_router"]

    # 2. Accuracy & Success check
    assert t1.total_queries == 5
    assert ht.total_queries == 5
    assert caar.total_queries == 5

    # Highest-tier should achieve high accuracy
    assert ht.accuracy_pct >= 80.0
    # CAAR should achieve high accuracy matching highest-tier
    assert caar.accuracy_pct >= 80.0

    # 3. Cost & Latency check
    assert t1.total_cost_usd > 0.0
    assert ht.total_cost_usd > 0.0
    assert caar.total_cost_usd > 0.0

    # Highest-tier (T4 Consensus) must be more expensive than Tier 1
    assert ht.total_cost_usd > t1.total_cost_usd
    # CAAR must achieve substantial cost savings vs Highest-tier
    assert caar.total_cost_usd < ht.total_cost_usd
    assert caar.cost_savings_vs_highest_usd > 0.0
    assert caar.cost_savings_vs_highest_pct > 0.0

    # Tier 1 must be fastest
    assert t1.avg_latency_ms < ht.avg_latency_ms
    # CAAR avg latency should be faster than highest-tier alone
    assert caar.avg_latency_ms < ht.avg_latency_ms

    # 4. Confidence & Escalation check
    assert 0.0 <= t1.avg_confidence <= 1.0
    assert 0.0 <= ht.avg_confidence <= 1.0
    assert 0.0 <= caar.avg_confidence <= 1.0
    assert 0.0 <= caar.escalation_rate_pct <= 100.0


def test_markdown_report_formatting():
    """Verify that format_benchmark_markdown_report generates a valid Markdown table with all columns."""
    sample_metrics = StrategyMetrics(
        strategy_name="Test Strategy",
        total_queries=10,
        successful_queries=9,
        accuracy_pct=90.0,
        total_cost_usd=0.005,
        avg_cost_per_query_usd=0.0005,
        total_latency_ms=5000,
        avg_latency_ms=500.0,
        avg_confidence=0.92,
        escalation_rate_pct=20.0,
        cost_savings_vs_highest_usd=0.02,
        cost_savings_vs_highest_pct=80.0,
        category_breakdown={"factual": {"accuracy_pct": 100.0, "avg_cost_usd": 0.0001, "avg_latency_ms": 400.0}}
    )

    report = BenchmarkReport(
        timestamp="2026-08-17 12:00:00 UTC",
        total_items=10,
        categories=["factual"],
        strategies={
            "tier_1_only": sample_metrics,
            "highest_tier_only": sample_metrics,
            "cost_aware_router": sample_metrics,
        },
        item_results=[]
    )

    md_output = format_benchmark_markdown_report(report)

    assert "Cost-Aware Agent Router (CAAR) — Evaluation & Benchmark Report" in md_output
    assert "Success / Accuracy" in md_output
    assert "Total Cost (USD)" in md_output
    assert "Cost Savings vs T4" in md_output
    assert "Avg Latency (ms)" in md_output
    assert "Escalation Rate" in md_output
    assert "Category-Wise Breakdown" in md_output
