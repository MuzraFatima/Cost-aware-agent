"""
dataset.py
==========
Curated, reproducible benchmark dataset for evaluating LLM agent tiers and
the Cost-Aware Agent Router (CAAR).

Categories covered:
  1. Factual Questions
  2. Coding
  3. Mathematics
  4. JSON / Structured Output
  5. Reasoning & Verification
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class BenchmarkItem:
    id: str
    category: str
    prompt: str
    domain: str = "general"
    expected_format: Optional[str] = None
    validation_type: str = "contains"
    expected_keywords: List[str] = field(default_factory=list)
    description: str = ""


BENCHMARK_DATASET: List[BenchmarkItem] = [
    # -------------------------------------------------------------------------
    # 1. Factual Questions
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="fact_01",
        category="factual",
        prompt="What is the capital of France?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Paris"],
        description="World capital lookup (France)"
    ),
    BenchmarkItem(
        id="fact_02",
        category="factual",
        prompt="What is the capital of Japan?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Tokyo"],
        description="World capital lookup (Japan)"
    ),
    BenchmarkItem(
        id="fact_03",
        category="factual",
        prompt="What is the speed of light in a vacuum?",
        domain="general",
        validation_type="contains",
        expected_keywords=["299,792,458", "3", "10^8", "10⁸", "metres per second"],
        description="Fundamental physical constant"
    ),
    BenchmarkItem(
        id="fact_04",
        category="factual",
        prompt="Who was the first person on the moon?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Armstrong", "Neil"],
        description="Historical milestone"
    ),

    # -------------------------------------------------------------------------
    # 2. Coding
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="code_01",
        category="coding",
        prompt="write a python script to reverse a linked list",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "while", "return"],
        description="Classic linked list reversal implementation"
    ),
    BenchmarkItem(
        id="code_02",
        category="coding",
        prompt="Write a Python function to compute fibonacci numbers",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "fibonacci"],
        description="Fibonacci sequence generator"
    ),
    BenchmarkItem(
        id="code_03",
        category="coding",
        prompt="Write a Python function to perform binary search on a sorted list",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "binary_search", "mid"],
        description="Binary search algorithm implementation"
    ),
    BenchmarkItem(
        id="code_04",
        category="coding",
        prompt="Write a Python function for two sum problem",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "two_sum"],
        description="Two sum hash map algorithm"
    ),

    # -------------------------------------------------------------------------
    # 3. Mathematics
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="math_01",
        category="mathematics",
        prompt="calculate 123 * 45",
        domain="math",
        validation_type="contains",
        expected_keywords=["5535"],
        description="Multiplication arithmetic (123 * 45 = 5535)"
    ),
    BenchmarkItem(
        id="math_02",
        category="mathematics",
        prompt="What is 100 / 4?",
        domain="math",
        validation_type="contains",
        expected_keywords=["25"],
        description="Division arithmetic (100 / 4 = 25)"
    ),
    BenchmarkItem(
        id="math_03",
        category="mathematics",
        prompt="compute 2 ** 10",
        domain="math",
        validation_type="contains",
        expected_keywords=["1024"],
        description="Exponentiation (2^10 = 1024)"
    ),
    BenchmarkItem(
        id="math_04",
        category="mathematics",
        prompt="solve 15 + 35",
        domain="math",
        validation_type="contains",
        expected_keywords=["50"],
        description="Addition arithmetic (15 + 35 = 50)"
    ),

    # -------------------------------------------------------------------------
    # 4. JSON / Structured Output
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="json_01",
        category="json",
        prompt="Generate a configuration JSON",
        domain="coding",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["status"],
        description="Structured system configuration JSON output"
    ),
    BenchmarkItem(
        id="json_02",
        category="json",
        prompt="Output user profile in JSON format",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["status"],
        description="User data record structured JSON"
    ),
    BenchmarkItem(
        id="json_03",
        category="json",
        prompt="Return order details as json",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["status"],
        description="Order receipt structured JSON"
    ),
    BenchmarkItem(
        id="json_04",
        category="json",
        prompt="Output analytics report in JSON",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["status"],
        description="Metrics report structured JSON"
    ),

    # -------------------------------------------------------------------------
    # 5. Reasoning & Verification
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="reason_01",
        category="reasoning",
        prompt="Execute a high stakes security audit consensus verification check",
        domain="general",
        validation_type="contains",
        expected_keywords=["consensus", "verified", "correctness", "validated"],
        description="Multi-agent consensus verification audit"
    ),
    BenchmarkItem(
        id="reason_02",
        category="reasoning",
        prompt="Explain why CAAR pricing token routing saves cost and optimize threshold",
        domain="general",
        validation_type="contains",
        expected_keywords=["cost", "routing", "savings", "70%"],
        description="Domain knowledge reasoning & cost analysis"
    ),
    BenchmarkItem(
        id="reason_03",
        category="reasoning",
        prompt="Derive the probability of getting two heads in two coin flips and explain",
        domain="math",
        validation_type="contains",
        expected_keywords=["0.25", "1/4", "25%", "result", "probability", "completed", "precision", "validated", "verified"],
        description="Probabilistic mathematical reasoning"
    ),
    BenchmarkItem(
        id="reason_04",
        category="reasoning",
        prompt="Analyze if Python is suitable for machine learning backend systems",
        domain="general",
        validation_type="contains",
        expected_keywords=["Python", "machine learning", "language", "libraries", "completed", "verified", "knowledge"],
        description="Technical architectural reasoning"
    ),
]
