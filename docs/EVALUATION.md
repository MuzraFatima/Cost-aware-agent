# CAAR Evaluation Methodology

## Purpose

The benchmark suite (`backend/app/evaluation/`) provides a reproducible, fully automated comparison of three routing strategies on a curated fixed dataset. It runs entirely in mock mode — no API keys or real LLM calls required.

---

## Dataset

**File:** `backend/app/evaluation/dataset.py`

20 queries across 5 categories (4 per category):

| Category | Prompts | Validation |
|---|---|---|
| `factual` | Capital cities, geography | `contains` — checks for keyword in response |
| `coding` | Python functions, fibonacci, string reversal | `python_code` — syntax-checks extracted code block |
| `math` | Arithmetic, multiplication | `contains` — checks numeric result |
| `json` | Config/JSON structured output | `json_valid` — parses response as JSON |
| `reasoning` | Multi-step, probability, temporal reasoning | `contains` — keyword match |

Each `BenchmarkItem` has:
```python
@dataclass
class BenchmarkItem:
    id: str
    category: str
    prompt: str
    domain: str = "general"
    expected_format: Optional[str] = None
    validation_type: str = "contains"      # "contains" | "python_code" | "json_valid"
    expected_keywords: List[str] = []
    description: str = ""
```

---

## Validation Logic

**File:** `backend/app/evaluation/evaluator.py` — `BenchmarkEvaluator._validate_response()`

| `validation_type` | Pass Condition |
|---|---|
| `contains` | All `expected_keywords` found in response text (case-insensitive) |
| `python_code` | Python code block extracted from response compiles without `SyntaxError` |
| `json_valid` | Response text (or code block) parses as valid JSON via `json.loads()` |

---

## Strategies Compared

| Strategy Key | Description |
|---|---|
| `"Tier 1 Only"` | Runs every query through `CheapAgent` only — no escalation |
| `"Highest-Tier Only"` | Runs every query through `ConsensusAgent` (Tier 4) only |
| `"Cost-Aware Router"` | Full CAAR cascade — starts at Tier 1, escalates on low confidence |

Each strategy is run independently against the full 20-query dataset.

---

## Metrics Collected

Per query result (`QueryResult` dataclass):
- `is_success` — whether validation passed
- `confidence_score` — final composite confidence from `ConfidenceEvaluator`
- `cost` — token cost in USD
- `latency_ms` — wall-clock milliseconds
- `final_tier` — tier at which response was accepted
- `escalated` — `True` if tier > 1

Per strategy aggregate (`StrategyMetrics` dataclass):
- `accuracy_pct` — `successful_queries / total_queries × 100`
- `total_cost_usd`, `avg_cost_per_query_usd`
- `avg_latency_ms`
- `avg_confidence_score`
- `escalation_rate_pct`
- `cost_savings_vs_baseline_usd`, `cost_savings_vs_baseline_pct`

---

## Running the Benchmark

```powershell
# Standard run (saves to BENCHMARK_REPORT.md)
python run_benchmark.py

# Custom output paths
python run_benchmark.py --output my_report.md --json-output results.json
```

Results are printed to stdout and saved to `BENCHMARK_REPORT.md`.

---

## Interpreting Results

| Outcome | Likely Cause |
|---|---|
| Tier 1 Only accuracy < 100% | Normal — cheap model fails JSON, complex reasoning |
| CAAR accuracy ≥ Tier 1 Only | Escalation correctly identified and recovered failures |
| CAAR cost < Highest-Tier | Simple queries resolved cheaply; only hard queries escalated |
| CAAR escalation rate ≈ 15% | Expected on a mixed dataset — most factual/simple queries resolve at T1 |

---

## Automated Tests for Evaluation Module

`tests/test_benchmark.py` verifies:

| Test | What it checks |
|---|---|
| `test_benchmark_dataset_coverage` | Dataset has ≥ 20 items across ≥ 5 categories |
| `test_benchmark_dataset_item_fields` | Every item has required fields populated |
| `test_validator_json_success` | Valid JSON string passes `json_valid` validation |
| `test_validator_json_malformed_failure` | Malformed JSON fails validation |
| `test_validator_python_code_success` | Valid Python block passes `python_code` validation |
| `test_validator_python_code_syntax_error` | Invalid Python fails validation |
| `test_validator_contains_keywords` | Keyword matching works case-insensitively |
| `test_benchmark_subset_execution` | A 2-item subset completes without error |
| `test_markdown_report_formatting` | Report contains expected sections and data |
