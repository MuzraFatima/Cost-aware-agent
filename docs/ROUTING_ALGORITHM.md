# CAAR Routing Algorithm Reference

## Overview

The routing algorithm in `backend/app/core/router_engine.py` implements a greedy confidence-based cascade: try the cheapest tier first, evaluate confidence, escalate if insufficient. A budget guard halts escalation once cumulative cost exceeds a per-request cap.

---

## Step 1 — Complexity Pre-Classification

Before entering the cascade, `classify_complexity(prompt, domain)` performs a fast keyword scan to skip obviously-too-cheap tiers:

```python
extreme_indicators = ["consensus verification", "bulletproof report", "high stakes", "audit", "security audit"]
# → start at Tier 4

math_indicators    = ["derive", "integral", "theorem", "calculate the probability", "solve equation"]
coding_indicators  = ["write a python script", "class interface", "refactor this code", "sql query for", "json schema"]
# → start at Tier 3

rag_indicators     = ["pricing", "cost details", "threshold configurations", "developer team"]
# → start at Tier 2

domain == "coding" or "math"  → start at Tier 3
domain == "creative"          → start at Tier 1

# Default                     → Tier 1
```

This avoids paying Tier 1 + Tier 2 latency for queries that will obviously need Tier 3/4.

---

## Step 2 — Threshold Lookup

```python
threshold = get_threshold(domain, db)
```

Reads the `routing_policies` table for the matching domain. Falls back to `settings.DEFAULT_THRESHOLDS` if no DB policy exists:

| Domain | Default |
|---|---|
| `general` | 0.65 |
| `creative` | 0.50 |
| `coding` | 0.85 |
| `math` | 0.85 |

---

## Step 3 — Cascade Loop

```python
current_tier = start_tier
while current_tier <= 4:
    res = await agent.execute(prompt, expected_format)
    confidence = await ConfidenceEvaluator.calculate_confidence(
        prompt, res["text"], expected_format, use_judge=False
    )
    steps_trace.append({...})
    total_cost += res["cost"]

    if confidence >= threshold:
        break                      # Accept this response

    if budget_limit_usd is not None and total_cost >= budget_limit_usd:
        break                      # Budget exhausted

    current_tier += 1              # Escalate
```

### Agent Failure Handling

If `agent.execute()` raises an exception, the router:
1. Records a failed step with `confidence_score=0.0`, `cost=0.0`, and `model_name="<name> (FAILED)"`
2. Continues to the next tier (does NOT raise or abort)

This guarantees a response is always returned unless **all four tiers** fail simultaneously, in which case a `RuntimeError` is raised.

---

## Step 4 — Cost Savings Calculation

```python
total_tokens   = sum(s["tokens_input"] + s["tokens_output"] for s in steps_trace)
frontier_cost  = estimate_frontier_cost(total_tokens)   # always gpt-4o pricing
cost_savings   = max(frontier_cost - total_cost, 0.0)
```

The frontier baseline is calculated as if all tokens were processed by gpt-4o at `$10/M` average, regardless of what model was actually used.

---

## Step 5 — Persistence

```python
RoutingLog(prompt, response, total_cost, estimated_frontier_cost,
           cost_savings, total_latency_ms, final_tier)
RoutingStep(tier, model_name, confidence_score, tokens_input,
            tokens_output, cost, latency_ms)  # one per step
```

---

## Confidence Evaluator

`backend/app/core/confidence.py`

```
calculate_confidence(prompt, response_text, expected_format, use_judge)
  │
  ├─ evaluate_syntactic(response_text, expected_format)
  │    JSON expected?
  │      Valid JSON             → 1.0
  │      JSON in markdown block → 0.9
  │      Invalid JSON           → 0.0  (hard fail)
  │    Python expected?
  │      Valid syntax           → min(score, 1.0)
  │      SyntaxError            → min(score, 0.2)
  │    Otherwise                → 1.0
  │
  ├─ evaluate_semantic_hedging(response_text)
  │    Scans 16 uncertainty patterns (regex)
  │    0 matches → 1.0
  │    1 match   → 0.70
  │    2 matches → 0.40
  │    3+ matches→ 0.10
  │
  ├─ IF syntactic_score ≤ 0.2:
  │    RETURN syntactic_score   (fast-fail, skip hedging)
  │
  ├─ base_confidence = 0.4 × syntactic + 0.6 × hedging
  │
  └─ IF use_judge:
       judge_score = evaluate_llm_judge(prompt, response_text)
       RETURN 0.5 × base + 0.5 × judge_score
     ELSE:
       RETURN base_confidence
```

---

## Policy Feedback Loop

After a user submits feedback via `POST /api/v1/router/feedback`:

```
score < 0.5  →  threshold += 0.05  (cap at 0.95)   # penalise: require higher confidence
score ≥ 0.5  →  threshold -= 0.01  (floor at 0.40)  # reward: relax threshold slightly
```

The domain is inferred from keywords in the original prompt text.
