#!/usr/bin/env python3
"""
run_benchmark.py
================
Command-line evaluation & benchmarking runner for Cost-Aware Agent Router (CAAR).

Executes the standardized reproducible benchmark comparing:
  1. Tier 1 Only (Commodity fast agent)
  2. Highest-tier Only (Consensus loop agent)
  3. Cost-Aware Agent Router (CAAR dynamic cascade)

Usage:
  python run_benchmark.py
  python run_benchmark.py --output BENCHMARK_REPORT.md
  python run_benchmark.py --json-output benchmark_results.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import asdict
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


async def main_async(output_md: Optional[str] = "BENCHMARK_REPORT.md", output_json: Optional[str] = None):
    print("=" * 70)
    print("Starting CAAR Evaluation & Benchmark Suite")
    print("=" * 70)
    print("Evaluating 3 Strategies across 5 Categories:")
    print("  - Factual Questions")
    print("  - Coding")
    print("  - Mathematics")
    print("  - JSON / Structured Output")
    print("  - Reasoning & Verification\n")

    start_time = time.time()
    evaluator = BenchmarkEvaluator()
    report = await evaluator.run_full_benchmark()
    elapsed = time.time() - start_time

    # Generate Markdown Report
    md_content = format_benchmark_markdown_report(report)

    # Print to console
    print("\n" + md_content + "\n")
    print(f"Benchmark completed in {elapsed:.2f} seconds.")

    # Save Markdown file
    if output_md:
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Markdown report saved to: {output_md}")

    # Save JSON file if requested
    if output_json:
        report_dict = asdict(report)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)
        print(f"JSON results saved to: {output_json}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Run evaluation benchmark comparing Tier 1, Highest-Tier, and Cost-Aware Agent Router."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="BENCHMARK_REPORT.md",
        help="Path to save the Markdown benchmark report (default: BENCHMARK_REPORT.md)"
    )
    parser.add_argument(
        "--json-output", "-j",
        type=str,
        default=None,
        help="Optional path to save full benchmark results as JSON"
    )
    args = parser.parse_args()

    asyncio.run(main_async(output_md=args.output, output_json=args.json_output))


if __name__ == "__main__":
    main()
