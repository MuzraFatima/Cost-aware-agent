# Cost-Aware Agent Router (CAAR) — Evaluation & Benchmark Report

*Generated on: `2026-08-18 16:37:38 UTC` | Benchmark Size: `20 queries` across 5 categories*

## Executive Summary Comparison Table

| Metric | Tier 1 Only | Highest-Tier Only (T4) | Cost-Aware Router (CAAR) |
| :--- | :---: | :---: | :---: |
| **Success / Accuracy** | `80.0%` (16/20) | `100.0%` (20/20) | **`100.0%`** (20/20) |
| **Avg Confidence Score** | `0.80` | `0.80` | **`1.00`** |
| **Total Cost (USD)** | `$0.000358` | `$0.065707` | **`$0.009928`** |
| **Avg Cost / Query** | `$0.000018` | `$0.003285` | **`$0.000496`** |
| **Cost Savings vs T4** | `99.5%` ($0.065349) | `0.0%` ($0.00) | **`84.9%`** ($0.055779) |
| **Avg Latency (ms)** | `403 ms` | `2002 ms` | **`985 ms`** |
| **Escalation Rate** | `0.0%` (Fixed) | `0.0%` (Fixed) | **`15.0%`** (Dynamic) |

## Category-Wise Breakdown

| Category | Tier 1 Accuracy | Highest-Tier Accuracy | CAAR Accuracy | CAAR Avg Cost | CAAR Avg Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Coding** | `100%` | `100%` | **`100%`** | `$0.000986` | `1206 ms` |
| **Factual** | `100%` | `100%` | **`100%`** | `$0.000012` | `404 ms` |
| **Json** | `0%` | `100%` | **`100%`** | `$0.000267` | `1056 ms` |
| **Mathematics** | `100%` | `100%` | **`100%`** | `$0.000241` | `1204 ms` |
| **Reasoning** | `100%` | `100%` | **`100%`** | `$0.000976` | `1056 ms` |

## Key Insights & System Performance

1. **High Quality with Dramatic Cost Savings**:
   - CAAR achieves **100.0% accuracy** matching highest-tier performance.
   - Saves **84.9% in API billing** ($0.055779 saved vs Highest-Tier baseline).

2. **Smart Dynamic Escalation**:
   - Simple queries (Factual, Arithmetic) are resolved at **Tier 1 (400ms latency, minimal cost)**.
   - Complex queries (JSON output, multi-agent audits) are safely escalated to **Tier 3/4 with an escalation rate of 15.0%**.

3. **Elimination of Structural Failures**:
   - Tier 1 only fails on strict structured JSON (0% JSON accuracy).
   - CAAR automatically detects low syntactic confidence on malformed JSON and escalates to Frontier tiers, achieving **100% JSON accuracy**.
