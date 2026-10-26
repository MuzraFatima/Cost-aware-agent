#!/usr/bin/env python3
"""
run_benchmark.py
================
Command-line evaluation & benchmarking runner for Cost-Aware Agent Router (CAAR).

Executes the standardized reproducible benchmark comparing:
  1. Tier 1 Only           (commodity fast agent)
  2. Tier-3 Only           (single large-model frontier call)
  3. Tier-4 Consensus Only (multi-agent verification loop)
  4. Cost-Aware Agent Router (CAAR dynamic cascade)

Usage:
  python run_benchmark.py                               # mock mode, 1 run
  python run_benchmark.py --live                        # live API mode (requires keys)
  python run_benchmark.py --runs 3                      # 3 repeated runs, averaged
  python run_benchmark.py --output BENCHMARK_REPORT.md --json-output results.json
"""

import argparse
import asyncio
import json
import math
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app.evaluation.evaluator import BenchmarkEvaluator, format_benchmark_markdown_report
from backend.app.evaluation.dataset import BENCHMARK_DATASET


def _wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Returns the 95% Wilson score confidence interval for a proportion.
    Returns (lower, upper) as fractions in [0, 1].
    """
    if n == 0:
        return 0.0, 0.0
    p_hat = successes / n
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


async def main_async(
    output_md: Optional[str] = "BENCHMARK_REPORT.md",
    output_json: Optional[str] = None,
    runs: int = 1,
    live: bool = False,
):
    mode_label = "live" if live else "mock"
    run_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print("=" * 70)
    print(f"CAAR Evaluation & Benchmark Suite  |  mode={mode_label}  |  runs={runs}")
    print("=" * 70)
    print(f"Dataset: {len(BENCHMARK_DATASET)} queries across 5 categories")
    print(f"Strategies: Tier-1-Only | Tier-3-Only | Tier-4-Consensus | CAAR\n")

    all_reports = []
    for run_idx in range(runs):
        if runs > 1:
            print(f"--- Run {run_idx + 1}/{runs} ---")
        start_time = time.time()
        evaluator = BenchmarkEvaluator(mock_mode=not live)
        report = await evaluator.run_full_benchmark()
        elapsed = time.time() - start_time
        all_reports.append(report)
        print(f"  Completed in {elapsed:.1f}s")

        # Write per-run JSON if multiple runs requested
        if runs > 1 and output_json:
            per_run_path = output_json.replace(".json", f"_run{run_idx + 1}.json")
            with open(per_run_path, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2)
            print(f"  Per-run JSON saved: {per_run_path}")

    # Use last report (or the only one) as basis for the MD report
    final_report = all_reports[-1]

    # Compute Wilson CIs for CAAR accuracy across runs (if > 1 run)
    if runs > 1:
        caar_strategy = final_report.strategies["cost_aware_router"]
        n_per_run = caar_strategy.total_queries
        total_successes = sum(r.strategies["cost_aware_router"].successful_queries for r in all_reports)
        total_n = n_per_run * runs
        lo, hi = _wilson_ci(total_successes, total_n)
        print(
            f"\nCAAR Accuracy across {runs} runs: "
            f"{100 * total_successes / total_n:.1f}%  "
            f"[95% Wilson CI: {100*lo:.1f}% – {100*hi:.1f}%]"
        )

    # Generate Markdown Report
    md_content = format_benchmark_markdown_report(final_report)
    # Inject provenance header
    provenance_lines = [
        f"<!-- BENCHMARK PROVENANCE",
        f"     Date     : {run_timestamp}",
        f"     Mode     : {mode_label}",
        f"     Runs     : {runs}",
        f"     Queries  : {len(BENCHMARK_DATASET)} ({len(BENCHMARK_DATASET)//5} per category)",
        f"     Commit   : see `git rev-parse HEAD`",
        f"-->",
        "",
    ]
    md_content = "\n".join(provenance_lines) + md_content

    # Print to console
    print("\n" + md_content + "\n")

    # Save Markdown file
    if output_md:
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Markdown report saved to: {output_md}")

    # Save JSON file if requested
    if output_json:
        report_dict = asdict(final_report)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        print(f"JSON results saved to: {output_json}")

    return final_report


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run evaluation benchmark comparing Tier-1, Tier-3, Tier-4-Consensus, "
            "and Cost-Aware Agent Router (CAAR)."
        )
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="BENCHMARK_REPORT.md",
        help="Path to save the Markdown benchmark report (default: BENCHMARK_REPORT.md)",
    )
    parser.add_argument(
        "--json-output", "-j",
        type=str,
        default=None,
        help="Optional path to save full benchmark results as JSON",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Run in live API mode (requires provider API keys in .env). Default: mock mode.",
    )
    parser.add_argument(
        "--runs", "-n",
        type=int,
        default=1,
        help=(
            "Number of repeated benchmark runs to average over "
            "(default 1). Use 3+ for Wilson CI reporting."
        ),
    )
    args = parser.parse_args()

    asyncio.run(
        main_async(
            output_md=args.output,
            output_json=args.json_output,
            runs=args.runs,
            live=args.live,
        )
    )


if __name__ == "__main__":
    main()
