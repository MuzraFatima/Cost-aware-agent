# CAAR Demo Walkthrough

Follow these steps to demonstrate the full Cost-Aware Agent Router system from a fresh clone.

---

## Prerequisites

- Python 3.10+
- No API keys required (runs in mock/sandbox mode by default)

---

## Step 1 — Install

```powershell
git clone <repository-url>
cd cost-aware-agent-router

python -m venv venv
venv\Scripts\Activate.ps1

pip install -r backend/requirements.txt
```

---

## Step 2 — Start the Server

```powershell
python -m uvicorn backend.app.main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

---

## Step 3 — Open the Dashboard

Navigate to **http://localhost:8000** in your browser.

You will see the interactive dashboard with four tabs: **Analytics**, **Sandbox**, **Policies**, **Logs**.

---

## Step 4 — Demo: Cheap Query (Tier 1 resolved)

1. Click the **Sandbox** tab
2. In the prompt box, type: `What is the capital of France?`
3. Leave **Domain** as `General`, **Expected Format** as `None`
4. Click **Submit**

**Expected result:**
- Selected Tier: **1**
- Confidence: **1.00** (no hedging, plain text answer)
- Escalation Path: `[1]`
- Routing Reason: *Resolved at Tier 1 — confidence threshold met on first attempt*
- Cost: `< $0.001`

---

## Step 5 — Demo: JSON Escalation (Tier 1 → Tier 3)

1. In the prompt box, type: `Generate a configuration JSON`
2. Set **Expected Format** to `JSON`
3. Click **Submit**

**Expected result:**
- Tier 1 mock returns malformed JSON → confidence 0.0 → hard fail
- Escalates to Tier 3 (Frontier) which returns valid JSON
- Selected Tier: **3**
- Escalation Path: `[1, 2, 3]` or `[1, 3]` depending on domain

---

## Step 6 — Demo: Policy Adjustment

1. Click the **Policies** tab
2. Drag the **General** threshold slider from `0.65` to `0.95`
3. Click **Update**
4. Go back to **Sandbox** and submit: `What is the capital of Spain?`

**Expected result:**
- Tier 1 answer is factual but hedging score reduces confidence below 0.95
- Query escalates to a higher tier than it normally would
- Restore threshold to `0.65` after demonstrating

---

## Step 7 — Demo: Analytics Dashboard

1. Click the **Analytics** tab

After submitting a few prompts in Sandbox, you will see:
- **Total Requests** updated
- **Tier Distribution** chart showing T1 > T3
- **Cost Savings** accumulating vs. frontier baseline
- **Escalation Rate** around 10–30% depending on queries sent

---

## Step 8 — Demo: Routing Logs

1. Click the **Logs** tab
2. Expand any row by clicking the `▶` arrow

You will see:
- Full prompt and response text
- Per-step trace: tier, model name, confidence score, token counts, cost, latency
- Whether each step was Accepted (✓) or Escalated (↑)
- Escalation Path and Routing Reason

---

## Step 9 — Demo: API Directly

Open **http://localhost:8000/docs** to interact with the full API via Swagger UI.

Try `POST /api/v1/router/completions` with:
```json
{
  "prompt": "Write a Python function to reverse a string",
  "domain": "coding",
  "expected_format": "python"
}
```

The response shows `final_tier`, the full `routing_path`, `cost_savings_usd`, and more.

---

## Step 10 — Run the Benchmark

```powershell
python run_benchmark.py
```

This runs 20 curated queries across 3 strategies (Tier 1 only, Tier 4 only, CAAR dynamic) and saves results to `BENCHMARK_REPORT.md`.

**Expected headline results (mock mode):**
- CAAR accuracy: **100%**
- CAAR cost savings vs Tier 4: **~87%**
- CAAR escalation rate: **~15%**

---

## Step 11 — Run Tests

```powershell
python -m pytest
```

Expected:
```
37 passed, 2 skipped in ~50s
```

---

## Step 12 — (Optional) Enable Real LLMs

```powershell
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY or ANTHROPIC_API_KEY or GEMINI_API_KEY
python -m uvicorn backend.app.main:app --reload
```

When at least one real API key is configured, `is_mock_mode` returns `False` and all agents make real LLM calls. The routing logic, confidence evaluation, and dashboard behaviour are identical.
