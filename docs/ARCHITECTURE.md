# CAAR Architecture Reference

## Overview

Cost-Aware Agent Router (CAAR) is a FastAPI application that sits between a client and multiple LLM providers. It routes each request through a ranked sequence of agent tiers, stopping as soon as a tier produces a response that meets the configured confidence threshold.

---

## Component Diagram

```
Client
  │
  ▼ HTTP POST /api/v1/router/completions
┌──────────────────────────────────────────────────┐
│  FastAPI  (backend/app/main.py)                  │
│  ┌──────────┐  ┌────────────┐  ┌─────────────┐  │
│  │ /router  │  │ /analytics │  │   /config   │  │
│  └────┬─────┘  └──────┬─────┘  └──────┬──────┘  │
└───────│───────────────│───────────────│──────────┘
        │               │               │
        ▼               ▼               ▼
  RouterEngine    Analytics DB    PolicyManager
  (core/)         (analytics.py)  (config.py)
        │
        ├─ classify_complexity()
        │    → determine start tier (1–4)
        │
        ├─ get_threshold(domain, db)
        │    → read from routing_policies table
        │
        └─ WHILE current_tier ≤ 4:
               agent.execute(prompt, expected_format)
               ConfidenceEvaluator.calculate_confidence()
               IF confidence ≥ threshold: BREAK
               IF budget exceeded: BREAK
               current_tier += 1
                   │
                   ▼
             Log to routing_logs + routing_steps (SQLite)
             Return result dict
```

---

## Agent Tiers

| Tier | Class | Model (Default) | Strengths | Typical Cost |
|---|---|---|---|---|
| 1 | `CheapAgent` | gpt-4o-mini | Speed, simple factual queries | ~$0.00001/q |
| 2 | `RAGAgent` | gpt-4o-mini + KB | Knowledge-base lookup, context-aware answers | ~$0.00002/q |
| 3 | `FrontierAgent` | gpt-4o | Precision, structured output, complex reasoning | ~$0.0003/q |
| 4 | `ConsensusAgent` | gpt-4o-mini + gpt-4o | Cross-verification, audit-grade accuracy | ~$0.001/q |

All agents implement the same `BaseAgent` interface:
```python
async def execute(prompt, messages=None, expected_format=None) -> {
    "text", "model_name", "tokens_input", "tokens_output",
    "cost", "latency_ms", "tier"
}
```

---

## Database Schema

```sql
-- Stores one record per routing request
routing_logs (
    id                      TEXT PRIMARY KEY,   -- UUID
    prompt                  TEXT,
    response                TEXT,
    total_cost              REAL,
    estimated_frontier_cost REAL,
    cost_savings            REAL,
    budget_limit_usd        REAL,
    total_latency_ms        INTEGER,
    final_tier              INTEGER,
    eval_score              REAL,               -- 0.0 or 1.0 from feedback
    feedback_text           TEXT,
    created_at              DATETIME
)

-- One row per tier attempted within a request
routing_steps (
    id               TEXT PRIMARY KEY,
    routing_log_id   TEXT REFERENCES routing_logs(id),
    tier             INTEGER,
    model_name       TEXT,
    confidence_score REAL,
    tokens_input     INTEGER,
    tokens_output    INTEGER,
    cost             REAL,
    latency_ms       INTEGER,
    created_at       DATETIME
)

-- One row per routing domain; updated by feedback loop
routing_policies (
    id                       INTEGER PRIMARY KEY,
    domain                   TEXT UNIQUE,
    min_confidence_threshold REAL,
    updated_at               DATETIME
)
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Synchronous SQLAlchemy** | Keeps session management predictable; SQLite is local so async overhead is not worth it |
| **`expire_on_commit=False`** | Prevents detached-instance errors when accessing log IDs after commit |
| **StaticFiles mounted last** | Ensures `/docs`, `/redoc`, `/openapi.json` are registered as FastAPI routes first and are not intercepted by the catch-all |
| **`is_mock_mode` property** | Centralised mock detection — agents check this once rather than comparing key strings independently |
| **`_push_keys()` at import** | Keys are set idempotently at import time; agents call it again before each live completion to handle late env var injection |
| **`_migrate_columns()` in init_db** | Safely adds new columns to existing SQLite databases without dropping data |
