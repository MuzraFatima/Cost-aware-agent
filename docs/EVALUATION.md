# CAAR Evaluation Methodology

## Purpose

The benchmark suite (`backend/app/evaluation/`) provides a reproducible, fully automated comparison of four routing strategies on a curated fixed dataset. It runs entirely in **mock mode** — no API keys or real LLM calls required. Pass `--live` to `run_benchmark.py` for live-provider runs.

---

## Dataset

**File:** `backend/app/evaluation/dataset.py`

**42 queries** across 5 categories (≥6 per category):

| Category | Count | Source | License | Validation |
|---|---|---|---|---|
| `factual` | 10 | TriviaQA subset | Apache 2.0 | `contains` — keyword in response (case-insensitive) |
| `coding` | 8 | HumanEval subset | MIT (OpenAI 2021) | `python_code` — extracted block compiles without `SyntaxError` |
| `mathematics` | 8 | GSM8K subset | MIT (OpenAI 2021) | `contains` — exact numeric answer present |
| `json` | 6 | Original | N/A | `json_schema` — parses as valid JSON via `json.loads()` |
| `reasoning` | 6 | Original | N/A | `contains` — expected verification keywords present |

### Source Citations

| Source | Paper / Repository | License |
|---|---|---|
| **TriviaQA** | Joshi et al. 2017, [huggingface.co/datasets/trivia_qa](https://huggingface.co/datasets/trivia_qa) | Apache 2.0 |
| **HumanEval** | Chen et al. 2021, [github.com/openai/human-eval](https://github.com/openai/human-eval) | MIT |
| **GSM8K** | Cobbe et al. 2021, [github.com/openai/grade-school-math](https://github.com/openai/grade-school-math) | MIT |

> **Note**: Only public-domain short-answer items were used. No copyrighted long-form answers or training labels are reproduced.

Each `BenchmarkItem` has:
```python
@dataclass
class BenchmarkItem:
    id: str
    category: str
    prompt: str
    domain: str = "general"
    expected_format: Optional[str] = None
    validation_type: str = "contains"      # "contains" | "python_code" | "json_schema"
    expected_keywords: List[str] = []
    description: str = ""
    source: str = "original"              # "gsm8k" | "humaneval" | "triviaqa" | "original"
```

---

## Validation Logic

**File:** `backend/app/evaluation/evaluator.py` — `validate_item_response()`

| `validation_type` | Pass Condition |
|---|---|
| `contains` | At least one `expected_keyword` found case-insensitively in response |
| `python_code` | Python code block extracted from response compiles without `SyntaxError` |
| `json_schema` | Response text (or fenced code block) parses as valid JSON via `json.loads()` |

---

## Strategies Compared

| Strategy Key | Description |
|---|---|
| `"Tier 1 Only"` | Every query through `CheapAgent` (Tier 1) only — no escalation |
| `"Tier-3 Only (Single Frontier Call)"` | Every query through `FrontierAgent` (Tier 3, single large-model call) only |
| `"Tier-4 Consensus Only"` | Every query through `ConsensusAgent` (Tier 4, multi-agent loop) only |
| `"Cost-Aware Router (CAAR)"` | Full CAAR cascade — starts at Tier 1, escalates on low confidence |

Each strategy runs independently against the full dataset.

---

## Metrics Collected

Per query result (`QueryResult` dataclass):
- `is_success` — whether validation passed
- `confidence_score` — final composite confidence from `ConfidenceEvaluator`
- `cost` — token cost in USD
- `latency_ms` — wall-clock milliseconds
- `final_tier` — tier at which response was accepted
- `escalated` — `True` if routing escalated beyond start tier

Per strategy aggregate (`StrategyMetrics` dataclass):
- `accuracy_pct` — `successful_queries / total_queries × 100`
- `total_cost_usd`, `avg_cost_per_query_usd`
- `avg_latency_ms`
- `avg_confidence_score`
- `escalation_rate_pct`
- `cost_savings_vs_highest_usd` / `_pct` — savings vs Tier-4 Consensus Only
- `cost_savings_vs_tier3_usd` / `_pct` — savings vs Tier-3 Only

---

## Running the Benchmark

```bash
# Standard run — mock mode, saves to BENCHMARK_REPORT.md
python run_benchmark.py

# Live API mode (requires GROQ_API_KEY or other provider key in .env)
python run_benchmark.py --live

# 3 repeated runs with 95% Wilson CI on accuracy
python run_benchmark.py --runs 3

# Custom output paths
python run_benchmark.py --output my_report.md --json-output results.json
```

Results are printed to stdout and saved to `BENCHMARK_REPORT.md`.

---

## Pareto Analysis

![CAAR Cost vs. Accuracy Pareto](pareto.png)

*Mode: mock | Dataset: 42 queries | 5 categories | Date: 2026-10-26 | Commit: a45beec*

CAAR lies on the Pareto frontier: it matches Tier-4 Consensus accuracy (100%) at a fraction of the cost ($0.000496 vs $0.003285 per query).

---

## Confidence Calibration

CAAR uses `ConfidenceCalibrationService` (`backend/app/core/confidence_calibration.py`) to compute domain-adaptive weighted scores from four sub-dimensions:

| Dimension | Coding | Math | RAG | General |
|---|---|---|---|---|
| Syntactic | 0.50 | 0.45 | 0.10 | 0.20 |
| Semantic | 0.25 | 0.35 | 0.30 | 0.40 |
| Hedging | 0.15 | 0.20 | 0.20 | 0.40 |
| Factuality | 0.10 | 0.00 | 0.40 | 0.00 |

> **⚠️ Calibration Limitation**: The current implementation applies heuristic weights. It does **not** use a held-out reliability dataset to fit the weights empirically, and a formal reliability diagram (confidence bin vs. actual accuracy) has not been generated from real LLM predictions. The word "calibrated" in dashboard captions refers to configurable weight sliders, **not** statistical calibration. Future work will use Platt scaling or isotonic regression on a separate validation set.

---

## Interpreting Results

| Outcome | Likely Cause |
|---|---|
| Tier 1 Only accuracy < 100% | Normal — cheap model fails JSON structured output, complex reasoning |
| CAAR accuracy ≥ Tier 1 Only | Escalation correctly identified and recovered failures |
| CAAR cost < Tier-4 Consensus | Simple queries resolved cheaply; only hard queries escalated |
| CAAR escalation rate ≈ 15% | Expected on a mixed dataset — most factual/simple queries resolve at T1 |

---

## Automated Tests for Evaluation Module

`tests/test_benchmark.py` verifies:

| Test | What it checks |
|---|---|
| `test_benchmark_dataset_coverage` | Dataset has ≥ 20 items across ≥ 5 categories |
| `test_benchmark_dataset_item_fields` | Every item has required fields populated |
| `test_validator_json_success` | Valid JSON string passes `json_schema` validation |
| `test_validator_json_malformed_failure` | Malformed JSON fails validation |
| `test_validator_python_code_success` | Valid Python block passes `python_code` validation |
| `test_validator_python_code_syntax_error` | Invalid Python fails validation |
| `test_validator_contains_keywords` | Keyword matching works case-insensitively |
| `test_benchmark_subset_execution` | A 2-item subset completes without error |
| `test_markdown_report_formatting` | Report contains expected sections and data |
