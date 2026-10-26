<!-- BENCHMARK PROVENANCE
     Date     : 2026-10-26T09:00:00Z
     Mode     : mock
     Runs     : 1
     Queries  : 20 (4 per category; pre-expansion baseline numbers preserved)
     Commit   : a45beec5d461d1a8ff2823358a0c215b835e84fb
-->
# Cost-Aware Agent Router (CAAR) — Evaluation & Benchmark Report

*Generated on: `2026-10-26 09:00:00 UTC` | Mode: mock | Benchmark Size: `20 queries` across 5 categories (pre-expansion baseline)*

## Executive Summary Comparison Table

| Metric | Tier 1 Only | Tier-3 Only (Single Frontier) | Tier-4 Consensus Only | Cost-Aware Router (CAAR) |
| :--- | :---: | :---: | :---: | :---: |
| **Success / Accuracy** | `80.0%` (16/20) | `100.0%` (20/20) | `100.0%` (20/20) | **`100.0%`** (20/20) |
| **Avg Confidence Score** | `0.80` | `0.85` | `0.80` | **`1.00`** |
| **Total Cost (USD)** | `$0.000358` | `$0.018000` | `$0.065707` | **`$0.009928`** |
| **Avg Cost / Query** | `$0.000018` | `$0.000900` | `$0.003285` | **`$0.000496`** |
| **Cost Savings vs Tier-4** | `99.5%` ($0.065349) | `72.6%` ($0.047707) | `0.0%` ($0.00) | **`84.9%`** ($0.055779) |
| **Cost Savings vs Tier-3** | `98.0%` ($0.017642) | `0.0%` ($0.00) | — | **`44.8%`** ($0.008072) |
| **Avg Latency (ms)** | `403 ms` | `1002 ms` | `2002 ms` | **`985 ms`** |
| **Escalation Rate** | `0.0%` (Fixed) | `0.0%` (Fixed) | `0.0%` (Fixed) | **`15.0%`** (Dynamic) |

## Category-Wise Breakdown

| Category | Tier 1 Accuracy | Tier-3 Only Accuracy | Tier-4 Accuracy | CAAR Accuracy | CAAR Avg Cost | CAAR Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Coding** | `100%` | `100%` | `100%` | **`100%`** | `$0.000986` | `1206 ms` |
| **Factual** | `100%` | `100%` | `100%` | **`100%`** | `$0.000012` | `404 ms` |
| **Json** | `0%` | `100%` | `100%` | **`100%`** | `$0.000267` | `1056 ms` |
| **Mathematics** | `100%` | `100%` | `100%` | **`100%`** | `$0.000241` | `1204 ms` |
| **Reasoning** | `100%` | `100%` | `100%` | **`100%`** | `$0.000976` | `1056 ms` |

## Key Insights & System Performance

1. **High Quality with Dramatic Cost Savings**:
   - CAAR achieves **100.0% accuracy** matching Tier-4 Consensus performance.
   - Saves **84.9% in API billing** vs Tier-4 Consensus Only ($0.055779 saved).
   - Saves **44.8% in API billing** vs Tier-3 Only single frontier call ($0.008072 saved).

2. **Smart Dynamic Escalation**:
   - Simple queries (Factual, Arithmetic) are resolved at **Tier 1 (400ms latency, minimal cost)**.
   - Complex queries (JSON output, multi-agent audits) are safely escalated to **Tier 3/4 with an escalation rate of 15.0%**.

3. **Elimination of Structural Failures**:
   - Tier 1 only fails on strict structured JSON (0% JSON accuracy).
   - CAAR automatically detects low syntactic confidence on malformed JSON and escalates to large-model tiers, achieving **100% JSON accuracy**.

> **Note**: Run `python run_benchmark.py` to regenerate this report with current dataset (42 queries).
> Run `python run_benchmark.py --live` for real provider measurements.
