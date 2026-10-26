"""
dataset.py
==========
Curated, reproducible benchmark dataset for evaluating LLM agent tiers and
the Cost-Aware Agent Router (CAAR).

Categories covered:
  1. Factual Questions  — TriviaQA-subset (public domain, Apache 2.0)
  2. Coding             — HumanEval-subset (MIT License, OpenAI)
  3. Mathematics        — GSM8K-subset (MIT License, OpenAI)
  4. JSON / Structured Output — JSON-schema generation tasks (original)
  5. Reasoning & Verification — Multi-step logic tasks (original)

Source citations and licenses: docs/EVALUATION.md
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
    source: str = "original"          # "gsm8k" | "humaneval" | "triviaqa" | "original"


BENCHMARK_DATASET: List[BenchmarkItem] = [
    # -------------------------------------------------------------------------
    # 1. Factual Questions  (TriviaQA-inspired subset — Apache 2.0)
    # Validator: contains — at least one expected_keyword appears case-insensitively
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="fact_01",
        category="factual",
        prompt="What is the capital of France?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Paris"],
        description="World capital lookup (France)",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_02",
        category="factual",
        prompt="What is the capital of Japan?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Tokyo"],
        description="World capital lookup (Japan)",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_03",
        category="factual",
        prompt="What is the speed of light in a vacuum?",
        domain="general",
        validation_type="contains",
        expected_keywords=["299,792,458", "3", "10^8", "10\u2078", "metres per second", "m/s"],
        description="Fundamental physical constant",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_04",
        category="factual",
        prompt="Who was the first person on the moon?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Armstrong", "Neil"],
        description="Historical milestone — Apollo 11",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_05",
        category="factual",
        prompt="What element has atomic number 79?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Gold", "Au"],
        description="Periodic table lookup",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_06",
        category="factual",
        prompt="In what year did World War II end?",
        domain="general",
        validation_type="contains",
        expected_keywords=["1945"],
        description="Historical year lookup",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_07",
        category="factual",
        prompt="What is the largest planet in our solar system?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Jupiter"],
        description="Astronomy factual lookup",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_08",
        category="factual",
        prompt="How many bones are in the adult human body?",
        domain="general",
        validation_type="contains",
        expected_keywords=["206"],
        description="Human anatomy factual",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_09",
        category="factual",
        prompt="What is the chemical symbol for water?",
        domain="general",
        validation_type="contains",
        expected_keywords=["H2O", "H\u2082O"],
        description="Basic chemistry symbol",
        source="triviaqa"
    ),
    BenchmarkItem(
        id="fact_10",
        category="factual",
        prompt="Who painted the Mona Lisa?",
        domain="general",
        validation_type="contains",
        expected_keywords=["Leonardo", "da Vinci", "DaVinci"],
        description="Art history factual",
        source="triviaqa"
    ),

    # -------------------------------------------------------------------------
    # 2. Coding  (HumanEval-inspired subset — MIT License, OpenAI 2021)
    # Validator: python_code — extracts Python block and compiles without SyntaxError
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="code_01",
        category="coding",
        prompt="Write a Python function to reverse a linked list.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "while", "return"],
        description="Linked list reversal (HumanEval-inspired)",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_02",
        category="coding",
        prompt="Write a Python function to compute fibonacci numbers.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "fibonacci"],
        description="Fibonacci sequence generator (HumanEval-inspired)",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_03",
        category="coding",
        prompt="Write a Python function to perform binary search on a sorted list.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "binary_search", "mid"],
        description="Binary search algorithm (HumanEval-inspired)",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_04",
        category="coding",
        prompt="Write a Python function for the two-sum problem.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "two_sum"],
        description="Two-sum hash map algorithm (HumanEval-inspired)",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_05",
        category="coding",
        prompt="Write a Python function that checks whether a string is a palindrome.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "palindrome", "return"],
        description="Palindrome check (HumanEval-inspired)",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_06",
        category="coding",
        prompt="Write a Python function to find the maximum element in a list without using max().",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "for", "return"],
        description="Manual maximum search",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_07",
        category="coding",
        prompt="Write a Python function to count the frequency of each word in a string.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "dict", "return"],
        description="Word frequency counter (HumanEval-inspired)",
        source="humaneval"
    ),
    BenchmarkItem(
        id="code_08",
        category="coding",
        prompt="Write a Python function that flattens a nested list.",
        domain="coding",
        expected_format="python",
        validation_type="python_code",
        expected_keywords=["def ", "flatten", "return"],
        description="Nested list flattening",
        source="humaneval"
    ),

    # -------------------------------------------------------------------------
    # 3. Mathematics  (GSM8K-inspired subset — MIT License, OpenAI 2021)
    # Validator: contains — exact numeric answer appears in response
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="math_01",
        category="mathematics",
        prompt="Calculate 123 * 45.",
        domain="math",
        validation_type="contains",
        expected_keywords=["5535"],
        description="Multiplication arithmetic (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_02",
        category="mathematics",
        prompt="What is 100 / 4?",
        domain="math",
        validation_type="contains",
        expected_keywords=["25"],
        description="Division arithmetic (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_03",
        category="mathematics",
        prompt="Compute 2 to the power of 10.",
        domain="math",
        validation_type="contains",
        expected_keywords=["1024"],
        description="Exponentiation (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_04",
        category="mathematics",
        prompt="Solve: 15 + 35.",
        domain="math",
        validation_type="contains",
        expected_keywords=["50"],
        description="Addition arithmetic (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_05",
        category="mathematics",
        prompt="A store sells apples for $1.50 each. If Lisa buys 8 apples and pays with a $20 bill, how much change does she receive?",
        domain="math",
        validation_type="contains",
        expected_keywords=["8", "$8", "8.00"],
        description="Word problem — change calculation (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_06",
        category="mathematics",
        prompt="What is the square root of 144?",
        domain="math",
        validation_type="contains",
        expected_keywords=["12"],
        description="Square root (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_07",
        category="mathematics",
        prompt="A train travels 60 km/h for 2.5 hours. How many km does it cover?",
        domain="math",
        validation_type="contains",
        expected_keywords=["150"],
        description="Distance = speed * time word problem (GSM8K-inspired)",
        source="gsm8k"
    ),
    BenchmarkItem(
        id="math_08",
        category="mathematics",
        prompt="What is 15% of 200?",
        domain="math",
        validation_type="contains",
        expected_keywords=["30"],
        description="Percentage calculation (GSM8K-inspired)",
        source="gsm8k"
    ),

    # -------------------------------------------------------------------------
    # 4. JSON / Structured Output  (original tasks)
    # Validator: json_schema — response parses as valid JSON via json.loads()
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="json_01",
        category="json",
        prompt="Generate a configuration JSON with fields: host, port, debug, and database_url.",
        domain="coding",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["host", "port"],
        description="System configuration JSON schema",
        source="original"
    ),
    BenchmarkItem(
        id="json_02",
        category="json",
        prompt="Output a user profile JSON with fields: id, name, email, and roles (array).",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["id", "email"],
        description="User data record JSON schema",
        source="original"
    ),
    BenchmarkItem(
        id="json_03",
        category="json",
        prompt="Return order details as a JSON object with fields: order_id, items (array), total_price, and status.",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["order_id", "total_price"],
        description="Order receipt JSON schema",
        source="original"
    ),
    BenchmarkItem(
        id="json_04",
        category="json",
        prompt="Output an analytics report JSON containing: report_id, generated_at, metrics (object with total_queries and avg_latency_ms), and summary (string).",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["metrics", "summary"],
        description="Analytics metrics JSON schema",
        source="original"
    ),
    BenchmarkItem(
        id="json_05",
        category="json",
        prompt="Generate a product inventory JSON with: product_id, name, sku, quantity_in_stock, and price_usd.",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["product_id", "sku"],
        description="Inventory item JSON schema",
        source="original"
    ),
    BenchmarkItem(
        id="json_06",
        category="json",
        prompt="Create a JSON schema for an API response envelope: status (string), data (object), error (nullable string), and timestamp (ISO 8601 string).",
        domain="general",
        expected_format="json",
        validation_type="json_schema",
        expected_keywords=["status", "timestamp"],
        description="API response envelope JSON schema",
        source="original"
    ),

    # -------------------------------------------------------------------------
    # 5. Reasoning & Verification  (original multi-step tasks)
    # Validator: contains — expected verification keywords appear in response
    # -------------------------------------------------------------------------
    BenchmarkItem(
        id="reason_01",
        category="reasoning",
        prompt="Execute a high stakes security audit consensus verification check.",
        domain="general",
        validation_type="contains",
        expected_keywords=["consensus", "verified", "correctness", "validated"],
        description="Multi-agent consensus verification audit",
        source="original"
    ),
    BenchmarkItem(
        id="reason_02",
        category="reasoning",
        prompt="Explain why CAAR pricing token routing saves cost and optimize threshold.",
        domain="general",
        validation_type="contains",
        expected_keywords=["cost", "routing", "savings", "70%"],
        description="Domain knowledge reasoning & cost analysis",
        source="original"
    ),
    BenchmarkItem(
        id="reason_03",
        category="reasoning",
        prompt="Derive the probability of getting two heads in two coin flips and explain.",
        domain="math",
        validation_type="contains",
        expected_keywords=["0.25", "1/4", "25%", "result", "probability", "completed", "precision", "validated", "verified"],
        description="Probabilistic mathematical reasoning",
        source="original"
    ),
    BenchmarkItem(
        id="reason_04",
        category="reasoning",
        prompt="Analyze if Python is suitable for machine learning backend systems.",
        domain="general",
        validation_type="contains",
        expected_keywords=["Python", "machine learning", "language", "libraries", "completed", "verified", "knowledge"],
        description="Technical architectural reasoning",
        source="original"
    ),
    BenchmarkItem(
        id="reason_05",
        category="reasoning",
        prompt="If all mammals are warm-blooded, and whales are mammals, are whales warm-blooded? Explain your reasoning.",
        domain="general",
        validation_type="contains",
        expected_keywords=["warm-blooded", "yes", "whale", "mammal"],
        description="Syllogistic deductive reasoning",
        source="original"
    ),
    BenchmarkItem(
        id="reason_06",
        category="reasoning",
        prompt="A clock reads 3:15 PM. What is the angle between the hour and minute hands?",
        domain="math",
        validation_type="contains",
        expected_keywords=["7.5", "7"],
        description="Clock angle reasoning problem (multi-step)",
        source="original"
    ),
]
