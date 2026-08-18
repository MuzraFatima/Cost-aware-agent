"""
Evaluation & Benchmarking Package for Cost-Aware Agent Router.
"""

from backend.app.evaluation.dataset import BenchmarkItem, BENCHMARK_DATASET
from backend.app.evaluation.evaluator import (
    BenchmarkEvaluator,
    BenchmarkReport,
    StrategyMetrics,
    QueryResult,
    validate_item_response,
    format_benchmark_markdown_report,
)

__all__ = [
    "BenchmarkItem",
    "BENCHMARK_DATASET",
    "BenchmarkEvaluator",
    "BenchmarkReport",
    "StrategyMetrics",
    "QueryResult",
    "validate_item_response",
    "format_benchmark_markdown_report",
]
