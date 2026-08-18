# Cost-Aware Agent Router (CAAR)

A production-grade, confidence-based multi-agent routing system that dynamically routes LLM queries to the most cost-efficient model tier capable of producing a sufficiently confident answer — escalating to more powerful (and expensive) tiers only when necessary.

---

## Problem Statement

Modern LLM APIs present a cost/quality trade-off: cheap small models are fast and affordable but frequently produce low-confidence, hedging, or structurally invalid outputs for complex tasks; frontier models deliver high-quality results but cost 50–100× more per token. Naively routing all traffic to a frontier model wastes money; routing everything to a cheap model sacrifices quality.

**CAAR solves this by treating every request as a cascade**: start at the cheapest tier, evaluate output confidence, and escalate only if the answer does not meet the configured quality threshold.

---

## Project Objectives

- Achieve frontier-model accuracy while cutting API costs by **>80%** on real-world query mixes
- Make routing decisions fully observable through a live dashboard, logs, and audit trails
- Support zero-code deployment in mock/sandbox mode for development without API keys
- Allow per-domain confidence policy tuning through a live UI with instant feedback loops

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Client / Dashboard                │
│               (Static SPA at http://localhost:8000) │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────┐
│               FastAPI Application                   │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ /api/v1     │  │ /api/v1      │  │ /api/v1    │ │
│  │  /router    │  │  /analytics  │  │  /config   │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬──────┘ │
└─────────│────────────────│────────────────│─────────┘
          │                │                │
┌─────────▼────────────────▼────────────────▼─────────┐
│                  RouterEngine                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  Tier 1  │  │  Tier 2  │  │  Tier 3  │  Tier 4  │
│  │  Cheap   │→ │  RAG     │→ │ Frontier │→ Consensus│
│  │  Agent   │  │  Agent   │  │  Agent   │   Agent  │
│  └──────────┘  └──────────┘  └──────────┘           │
│              ConfidenceEvaluator                     │
│         (Syntactic + Semantic Hedging)               │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│               SQLite Database (caar.db)              │
│   routing_logs │ routing_steps │ routing_policies    │
└─────────────────────────────────────────────────────┘
```

### Module Map

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI app factory, lifespan, route mounting |
| `backend/app/core/router_engine.py` | Cascade loop, tier selection, cost/latency tracking |
| `backend/app/core/confidence.py` | Syntactic + semantic hedging evaluators |
| `backend/app/core/config.py` | Pydantic settings (env vars, defaults, mock detection) |
| `backend/app/agents/cheap_agent.py` | Tier 1 — fast/cheap model (gpt-4o-mini) |
| `backend/app/agents/rag_agent.py` | Tier 2 — RAG-augmented retrieval agent |
| `backend/app/agents/frontier_agent.py` | Tier 3 — high-precision frontier model (gpt-4o) |
| `backend/app/agents/consensus_agent.py` | Tier 4 — multi-agent consensus + verification loop |
| `backend/app/agents/_mock_answers.py` | Deterministic mock responses for all tiers (no API keys needed) |
| `backend/app/api/router.py` | POST `/completions` and POST `/feedback` endpoints |
| `backend/app/api/analytics.py` | GET `/summary` and GET `/logs` endpoints |
| `backend/app/api/config.py` | GET/PUT `/policies` for live threshold management |
| `backend/app/db/models.py` | SQLAlchemy ORM: `RoutingLog`, `RoutingStep`, `RoutingPolicy` |
| `backend/app/db/session.py` | Engine, session factory, `init_db()`, schema migrations |
| `backend/app/utils/cost_tracker.py` | Token cost calculation with local + LiteLLM pricing |
| `backend/app/utils/llm_client.py` | Centralised LiteLLM key propagation |
| `backend/app/evaluation/` | Benchmark dataset, evaluator, and report formatter |
| `backend/app/static/` | Dashboard HTML/CSS/JS (served at `/`) |
| `run_benchmark.py` | CLI benchmark runner |
| `tests/` | Pytest test suite (39 tests) |

---

## Tier-Based Routing Workflow

Every incoming request flows through the following cascade:

```
Request
  │
  ├─ classify_complexity()
  │    Keyword + domain heuristics → determines start tier (1–4)
  │
  ▼
Tier 1: Cheap Direct Agent  ──────────────────────────────────────┐
  │  Fast mini model (gpt-4o-mini). 400ms simulated latency.       │
  │  Cost: ~$0.00001/query                                         │
  │                                                                │
  ▼ ConfidenceEvaluator                                            │
  │  confidence ≥ threshold? ──YES──► Return response (DONE)       │
  │                                                                │
  NO (escalate)                                                    │
  │                                                                │
Tier 2: RAG-Augmented Agent ──────────────────────────────────────┤
  │  Retrieves context from knowledge base, re-runs query.         │
  │  600ms simulated latency.                                      │
  │                                                                │
  ▼ ConfidenceEvaluator                                            │
  │  confidence ≥ threshold? ──YES──► Return response (DONE)       │
  │                                                                │
  NO (escalate)                                                    │
  │                                                                │
Tier 3: Frontier Single Agent ────────────────────────────────────┤
  │  High-precision frontier model (gpt-4o), low temperature.      │
  │  1200ms simulated latency. Cost: ~$0.0003/query                │
  │                                                                │
  ▼ ConfidenceEvaluator                                            │
  │  confidence ≥ threshold? ──YES──► Return response (DONE)       │
  │                                                                │
  NO (escalate)                                                    │
  │                                                                │
Tier 4: Consensus & Verify Loop ─────────────────────────────────┘
  │  Runs T1 + T3 concurrently, synthesises with a critic pass.
  │  2000ms simulated latency. Always returns. Always the last tier.
  │
  ▼
  Return response (DONE)
```

---

## Confidence-Based Escalation

The `ConfidenceEvaluator` computes a composite score `[0.0, 1.0]` from two signals:

### 1. Syntactic Score
| Condition | Score |
|---|---|
| Valid JSON (when JSON expected) | 1.0 |
| JSON in markdown block | 0.9 |
| Invalid JSON (when JSON expected) | 0.0 → forced escalation |
| Valid Python syntax | 1.0 |
| Python syntax error | 0.2 |
| Plain text | 1.0 |

### 2. Semantic Hedging Score
Scans response text for uncertainty markers (`"I'm not sure"`, `"probably"`, `"cannot guarantee"`, `"please verify"`, etc.):

| Hedge matches | Score |
|---|---|
| 0 | 1.0 |
| 1 | 0.70 |
| 2 | 0.40 |
| 3+ | 0.10 |

### Final Composite Score

```
base_confidence = (0.4 × syntactic_score) + (0.6 × hedging_score)
```

If `syntactic_score ≤ 0.2`, the syntactic score is returned directly (hard fail → immediate escalation).

An optional **LLM Judge** mode (`use_judge=True`) blends in a cheap judge model's score at 50% weight for production use.

### Per-Domain Thresholds (Defaults)

| Domain | Threshold | Rationale |
|---|---|---|
| `general` | 0.65 | Permissive — most queries are straightforward |
| `creative` | 0.50 | Creative outputs tolerate uncertainty |
| `coding` | 0.85 | Code must be syntactically valid |
| `math` | 0.85 | Numerical answers require high precision |

Thresholds are stored in SQLite and adjustable in real time through the Policies tab in the dashboard.

---

## Cost-Aware Routing

### Token Cost Calculation

Each agent step reports its cost using `calculate_token_cost()`:
1. Checks a local `FALLBACK_PRICING` dict (gpt-4o-mini, gpt-4o, Claude variants, mock models)
2. Falls back to `litellm.cost_per_token()` for any unlisted model
3. Falls back to a conservative estimate (`$1/M input, $5/M output`) if LiteLLM fails

### Cost Savings Calculation

After each routing run, the router calculates what the request *would have cost* if always sent directly to the Tier 3 frontier model:

```
frontier_cost  = total_tokens × $10.00/M   (gpt-4o avg)
cost_savings   = max(frontier_cost - actual_cost, 0.0)
savings_pct    = cost_savings / frontier_cost × 100
```

### Budget Guard

An optional `budget_limit_usd` parameter halts escalation once cumulative cost for that request reaches the cap, returning the best answer obtained so far.

---

## Evaluation & Benchmarking

### Benchmark Dataset

20 queries across 5 categories (4 per category):
- **Factual** — world capitals, geography lookups
- **Coding** — Python function generation, algorithm implementation
- **Mathematics** — arithmetic, reasoning
- **JSON** — structured output generation with schema validation
- **Reasoning** — multi-step verification problems

### Strategies Compared

| Strategy | Description |
|---|---|
| Tier 1 Only | All queries handled by the cheap fast agent |
| Highest-Tier Only | All queries handled by the Consensus agent (Tier 4) |
| CAAR (Dynamic) | Full confidence-based cascade routing |

### Latest Benchmark Results

| Metric | Tier 1 Only | Tier 4 Only | CAAR |
|---|---|---|---|
| Accuracy | 65% | 95% | **100%** |
| Avg Confidence | 0.80 | 0.80 | **1.00** |
| Total Cost | $0.000284 | $0.063022 | **$0.007996** |
| Cost Savings vs T4 | 99.5% | 0% | **87.3%** |
| Avg Latency | 400ms | 2000ms | **980ms** |
| Escalation Rate | 0% | 0% | **15%** |

### Running the Benchmark

```powershell
# Run full benchmark and save Markdown report
python run_benchmark.py

# Save both Markdown and JSON output
python run_benchmark.py --output BENCHMARK_REPORT.md --json-output results.json
```

---

## Dashboard Features

The interactive SPA dashboard is served at `http://localhost:8000/` and includes four tabs:

### Analytics Tab
- **Total Requests** — all-time routed query count
- **Aggregated Cost Spent** — cumulative token expenditure in USD
- **Estimated Savings** — dollars saved vs. routing everything to Tier 3
- **Avg Step Confidence** — average confidence score across all routing steps
- **Average Latency** — mean response time in milliseconds
- **Escalation Rate** — percentage of requests that escalated past Tier 1
- **Cost Efficiency Chart** — cumulative actual vs. frontier cost over time
- **Tier Distribution Chart** — doughnut chart of final tier selection ratios

### Sandbox Tab
- Submit prompts with domain and format specifiers
- Live cascade audit visualiser showing each step's confidence, cost, and pass/fail status
- **Routing Decision Summary** panel: selected tier, confidence, threshold, total cost, latency, escalation path, routing reason
- Thumbs-up/down feedback for policy adaptation

### Policies Tab
- Slider controls for per-domain confidence thresholds
- Changes persist to SQLite immediately and affect all subsequent routing

### Logs Tab
- Full routing history table with expandable rows
- Per-row: timestamp, prompt, final tier, escalation path (tier pill badges), cost, latency, routing reason, feedback
- Expanded row: full prompt, response, routing cascade trace (per-step confidence, tokens, cost, latency, escalation status), routing reason

---

## API Reference

Interactive Swagger docs: **`http://localhost:8000/docs`**
ReDoc: **`http://localhost:8000/redoc`**

### POST `/api/v1/router/completions`

Route a prompt through the agent cascade.

```json
{
  "prompt": "What is the capital of France?",
  "domain": "general",
  "expected_format": null,
  "budget_limit_usd": null
}
```

**Fields:**
- `prompt` *(required)* — the query text (must be non-empty)
- `domain` — `"general"` | `"coding"` | `"math"` | `"creative"` (default: `"general"`)
- `expected_format` — `"json"` | `"python"` | `null`
- `budget_limit_usd` — optional float; stops escalation when cumulative cost hits this cap

**Response:**
```json
{
  "id": "uuid",
  "text": "The capital of France is Paris.",
  "final_tier": 1,
  "threshold_used": 0.65,
  "usage": {
    "total_cost_usd": 0.0000012,
    "estimated_frontier_cost_usd": 0.000010,
    "cost_savings_usd": 0.0000088,
    "total_latency_ms": 401,
    "routing_path": [
      {
        "tier": 1,
        "model_name": "gpt-4o-mini (Simulated)",
        "confidence_score": 1.0,
        "tokens_input": 12,
        "tokens_output": 10,
        "cost": 0.0000012,
        "latency_ms": 401
      }
    ],
    "budget_limit_usd": null,
    "budget_exceeded": false
  }
}
```

### POST `/api/v1/router/feedback`

Submit quality feedback to trigger policy adaptation.

```json
{
  "routing_log_id": "uuid",
  "score": 1.0,
  "feedback_text": "Correct and concise"
}
```

### GET `/api/v1/analytics/summary`

Returns aggregated KPI metrics.

```json
{
  "total_requests": 42,
  "total_cost_spent": 0.000834,
  "total_estimated_frontier_cost": 0.006720,
  "cost_saved_vs_frontier_only": 0.005886,
  "average_latency_ms": 620,
  "average_confidence": 0.91,
  "escalation_rate": 0.143,
  "tier_distribution": {"tier_1": 0.86, "tier_2": 0.02, "tier_3": 0.10, "tier_4": 0.02}
}
```

### GET `/api/v1/analytics/logs?limit=50&offset=0`

Returns routing log records with full step traces, escalation paths, and routing reasons.

### GET `/api/v1/config/policies`

Returns all active per-domain confidence thresholds.

### PUT `/api/v1/config/policies`

Updates a domain threshold.

```json
{
  "domain": "coding",
  "min_confidence_threshold": 0.90
}
```

---

## Installation & Setup

### Prerequisites

- Python 3.10+ (tested on 3.14)
- pip

### 1. Clone and navigate to the project

```powershell
git clone <repository-url>
cd cost-aware-agent-router
```

### 2. Create and activate a virtual environment

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r backend/requirements.txt
```

### 4. Configure environment variables (optional)

The system runs fully in **mock/sandbox mode** by default — no API keys required. To enable real LLM calls, copy the template and fill in at least one key:

```powershell
Copy-Item .env.example .env
# Edit .env with your real API keys
```

Or set keys inline in PowerShell:

```powershell
$env:OPENAI_API_KEY    = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:GEMINI_API_KEY    = "AI..."
```

**Mock mode is active when all keys remain at their placeholder values.** Agents return deterministic, realistic responses from the built-in knowledge base — identical to real mode for UI and routing logic testing.

---

## Running the Project

Start the FastAPI server from the project root:

```powershell
python -m uvicorn backend.app.main:app --reload
```

| URL | What you'll find |
|---|---|
| `http://localhost:8000/` | Interactive Dashboard |
| `http://localhost:8000/docs` | Swagger / OpenAPI UI |
| `http://localhost:8000/redoc` | ReDoc API reference |
| `http://localhost:8000/api/v1/analytics/summary` | Raw JSON analytics |

The SQLite database (`caar.db`) is created automatically in the project root on first run. No migrations are needed.

---

## Running Tests

```powershell
python -m pytest
```

Expected output:

```
collected 39 items

tests\test_benchmark.py .........       [ 23%]
tests\test_e2e_live_path.py ........ss  [ 48%]
tests\test_llm_integration.py ......    [ 64%]
tests\test_router.py ..............     [100%]

37 passed, 2 skipped in ~50s
```

The 2 skipped tests (`test_live_api_*`) require real API keys to be configured and are automatically skipped in mock mode.

### Test Coverage

| File | What is tested |
|---|---|
| `test_router.py` | Confidence evaluator, complexity classifier, routing cascade, tier execution, graceful failure, schema validation, policy threshold effects, cost savings, budget guard |
| `test_e2e_live_path.py` | Full end-to-end pipeline per agent, mock fallback on error, JSON escalation, confidence escalation |
| `test_benchmark.py` | Dataset coverage, validator logic (JSON/Python/keywords), benchmark execution, report formatting |
| `test_llm_integration.py` | Mock mode detection, provider key propagation, LiteLLM environment setup |

---

## Limitations

- **Mock mode responses** are static keyword-matched answers. They do not call any LLM and are designed purely for development, testing, and UI demonstration.
- **RAG retrieval** (Tier 2) uses an in-memory keyword-based knowledge base rather than a real vector store. Production use would replace this with ChromaDB, Pinecone, or similar.
- **LLM Judge mode** (`use_judge=True`) is disabled by default. Enabling it adds one extra LLM call per routing step.
- **Confidence scoring** is heuristic-based (syntactic + hedging). It does not measure factual accuracy — a confidently wrong answer can still receive a high score.
- **SQLite** is used for local development. It does not support concurrent writes well under high load; switch to PostgreSQL for production.
- **Cost savings** are estimated against a fixed gpt-4o baseline, not the actual model being used by Tier 3 in production.

---

## Future Scope

- **Real vector store integration** — plug ChromaDB / Pinecone into the RAG agent (Tier 2) for domain-specific knowledge retrieval
- **Active LLM judge** — enable `use_judge=True` with a cheap judge model for factual accuracy measurement
- **Streaming responses** — return partial tokens to the dashboard as they are generated
- **Multi-turn conversation** — pass conversation history through the cascade for context-aware routing
- **Cost alerting** — email/webhook alerts when daily spend crosses a configurable threshold
- **Async PostgreSQL** — replace SQLite with `asyncpg` for production-grade concurrent persistence
- **A/B threshold testing** — automatically compare routing outcomes across threshold variants
- **OpenTelemetry tracing** — export per-request spans to Jaeger/Grafana for production observability
- **Docker & Compose** — containerise the app and database for one-command deployment

---

## Project Structure

```
cost-aware-agent-router/
├── backend/
│   ├── app/
│   │   ├── agents/           # All 4 tier agents + mock library
│   │   ├── api/              # FastAPI route handlers
│   │   ├── core/             # Router engine, confidence evaluator, config
│   │   ├── db/               # SQLAlchemy models and session management
│   │   ├── evaluation/       # Benchmark dataset, evaluator, formatter
│   │   ├── static/           # Dashboard (index.html, app.js, style.css)
│   │   ├── utils/            # Cost tracker, LLM client
│   │   └── main.py           # FastAPI app entry point
│   └── requirements.txt
├── tests/                    # Pytest test suite (39 tests)
├── run_benchmark.py          # CLI benchmark runner
├── BENCHMARK_REPORT.md       # Latest benchmark results
├── .env.example              # Environment variable template
├── caar.db                   # SQLite database (auto-created)
└── README.md
```