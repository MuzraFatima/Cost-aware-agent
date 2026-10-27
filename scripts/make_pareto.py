#!/usr/bin/env python3
"""
scripts/make_pareto.py
======================
Generates the Cost vs. Accuracy Pareto frontier chart (docs/pareto.png)
from the CAAR benchmark output (JSON or Markdown).

Usage:
    python scripts/make_pareto.py
    python scripts/make_pareto.py --input benchmark_results.json --output docs/pareto.png
    python scripts/make_pareto.py --input BENCHMARK_REPORT.md --output docs/pareto.png
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker


def get_git_commit() -> str:
    """Returns the current short git commit hash, or 'unknown'."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return out or "unknown"
    except Exception:
        return "unknown"


def parse_from_json(json_path: str) -> Tuple[Dict[str, Dict[str, float]], int, str, str]:
    """Extracts strategy metrics from a benchmark JSON report."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_items = data.get("total_items", 38)
    timestamp = data.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    date_str = timestamp.split()[0] if " " in timestamp else timestamp[:10]

    strategies_data = data.get("strategies", {})

    parsed = {}
    key_mapping = {
        "tier_1_only": "Tier-1 Only",
        "tier_3_only": "Tier-3 Only",
        "tier_4_consensus_only": "Tier-4 Consensus",
        "cost_aware_router": "CAAR",
    }

    for key, label in key_mapping.items():
        if key in strategies_data:
            s = strategies_data[key]
            parsed[label] = {
                "accuracy": float(s.get("accuracy_pct", 0.0)),
                "cost": float(s.get("avg_cost_per_query_usd", 0.0)),
            }

    return parsed, total_items, date_str, "mock"


def parse_from_markdown(md_path: str) -> Tuple[Dict[str, Dict[str, float]], int, str, str]:
    """Extracts strategy metrics from a BENCHMARK_REPORT.md file."""
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    total_items = 38
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mode_str = "mock"

    q_match = re.search(r"Queries\s*:\s*(\d+)", content)
    if q_match:
        total_items = int(q_match.group(1))
    else:
        q_match2 = re.search(r"Benchmark Size:\s*`(\d+)\s*queries`", content)
        if q_match2:
            total_items = int(q_match2.group(1))

    d_match = re.search(r"Date\s*:\s*([0-9\-]+)", content)
    if d_match:
        date_str = d_match.group(1)

    m_match = re.search(r"Mode\s*:\s*(\w+)", content)
    if m_match:
        mode_str = m_match.group(1)

    # Parse executive summary table
    parsed = {}
    acc_match = re.search(
        r"\|\s*\*\*Success\s*/\s*Accuracy\*\*\s*\|\s*`?([0-9\.]+)%?`?[^\|]*\|\s*`?([0-9\.]+)%?`?[^\|]*\|\s*`?([0-9\.]+)%?`?[^\|]*\|\s*\*\*`?([0-9\.]+)%?`?\*\*",
        content
    )
    cost_match = re.search(
        r"\|\s*\*\*Avg Cost\s*/\s*Query\*\*\s*\|\s*`?\$?([0-9\.]+)`?[^\|]*\|\s*`?\$?([0-9\.]+)`?[^\|]*\|\s*`?\$?([0-9\.]+)`?[^\|]*\|\s*\*\*`?\$?([0-9\.]+)`?\*\*",
        content
    )

    if acc_match and cost_match:
        accuracies = [float(acc_match.group(i)) for i in range(1, 5)]
        costs = [float(cost_match.group(i)) for i in range(1, 5)]
        labels = ["Tier-1 Only", "Tier-3 Only", "Tier-4 Consensus", "CAAR"]
        for label, acc, cost in zip(labels, accuracies, costs):
            parsed[label] = {"accuracy": acc, "cost": cost}

    return parsed, total_items, date_str, mode_str


def build_pareto_chart(
    data: Dict[str, Dict[str, float]],
    total_items: int,
    date_str: str,
    commit_hash: str,
    output_png: str,
    mode_str: str = "mock",
):
    """Generates and saves the dark-themed Pareto chart matching CAAR design."""
    os.makedirs(os.path.dirname(os.path.abspath(output_png)), exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=150)

    # Dark background
    bg_color = "#18181b"
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    # Strategy point styles
    styles = {
        "Tier-1 Only": {
            "marker": "o",
            "color": "#ef4444",
            "size": 220,
            "label": "Tier-1 Only",
            "edgecolor": "white",
            "lw": 1.0,
        },
        "Tier-3 Only": {
            "marker": "^",
            "color": "#eab308",
            "size": 220,
            "label": "Tier-3 Only",
            "edgecolor": "white",
            "lw": 1.0,
        },
        "Tier-4 Consensus": {
            "marker": "s",
            "color": "#f97316",
            "size": 220,
            "label": "Tier-4 Consensus",
            "edgecolor": "white",
            "lw": 1.0,
        },
        "CAAR": {
            "marker": "*",
            "color": "#22c55e",
            "size": 850,
            "label": "CAAR",
            "edgecolor": "#14532d",
            "lw": 1.5,
        },
    }

    # Plot points
    for name, style in styles.items():
        if name in data:
            cost = data[name]["cost"]
            acc = data[name]["accuracy"]
            ax.scatter(
                cost,
                acc,
                color=style["color"],
                marker=style["marker"],
                s=style["size"],
                edgecolors=style["edgecolor"],
                linewidths=style["lw"],
                label=style["label"],
                zorder=5,
            )

    # Annotations
    if "Tier-1 Only" in data:
        t1 = data["Tier-1 Only"]
        ax.annotate(
            f"Tier-1 Only\n({t1['accuracy']:.1f}%, ${t1['cost']:.6f})",
            (t1["cost"], t1["accuracy"]),
            textcoords="offset points",
            xytext=(15, -15),
            color="#ffffff",
            fontsize=11,
            va="top",
            ha="left",
            bbox=dict(boxstyle="round,pad=0.2", fc="#27272a", ec="#3f3f46", alpha=0.8),
        )

    if "CAAR" in data:
        caar = data["CAAR"]
        ax.annotate(
            f"CAAR\n({caar['accuracy']:.1f}%, ${caar['cost']:.6f})",
            (caar["cost"], caar["accuracy"]),
            textcoords="offset points",
            xytext=(-15, 22),
            color="#4ade80",
            fontsize=11,
            fontweight="bold",
            va="bottom",
            ha="right",
            bbox=dict(boxstyle="round,pad=0.2", fc="#052e16", ec="#16a34a", alpha=0.9),
        )

    if "Tier-3 Only" in data:
        t3 = data["Tier-3 Only"]
        ax.annotate(
            f"Tier-3 Only\n({t3['accuracy']:.1f}%, ${t3['cost']:.6f})",
            (t3["cost"], t3["accuracy"]),
            textcoords="offset points",
            xytext=(15, -25),
            color="#ffffff",
            fontsize=11,
            va="top",
            ha="left",
            bbox=dict(boxstyle="round,pad=0.2", fc="#27272a", ec="#3f3f46", alpha=0.8),
        )

    if "Tier-4 Consensus" in data:
        t4 = data["Tier-4 Consensus"]
        ax.annotate(
            f"Tier-4 Consensus\n({t4['accuracy']:.1f}%, ${t4['cost']:.6f})",
            (t4["cost"], t4["accuracy"]),
            textcoords="offset points",
            xytext=(-20, -20),
            color="#ffffff",
            fontsize=11,
            va="top",
            ha="right",
            bbox=dict(boxstyle="round,pad=0.2", fc="#27272a", ec="#3f3f46", alpha=0.8),
        )

    # Pareto frontier line:
    # A point (c1, a1) is dominated if there exists (c2, a2) with c2 <= c1 and a2 >= a1 (and at least one strict).
    frontier_candidates = []
    for k, v in data.items():
        c1, a1 = v["cost"], v["accuracy"]
        dominated = False
        for k2, v2 in data.items():
            if k == k2:
                continue
            c2, a2 = v2["cost"], v2["accuracy"]
            if (c2 <= c1 and a2 >= a1) and (c2 < c1 or a2 > a1):
                dominated = True
                break
        if not dominated:
            frontier_candidates.append((c1, a1))

    frontier_candidates.sort(key=lambda p: p[0])

    if len(frontier_candidates) >= 2:
        fx = [p[0] for p in frontier_candidates]
        fy = [p[1] for p in frontier_candidates]
        ax.plot(
            fx,
            fy,
            linestyle="--",
            color="#4f86f7",
            linewidth=2.2,
            alpha=0.9,
            label="Pareto frontier",
            zorder=4,
        )

    # Titles and Subtitle
    title_text = f"CAAR Cost vs. Accuracy Pareto ({mode_str.title()} Mode)"
    subtitle_text = (
        f"Mode: {mode_str} | Dataset: {total_items} queries | 5 categories | "
        f"Date: {date_str} | Commit: {commit_hash}"
    )

    ax.set_title(f"{title_text}\n{subtitle_text}", fontsize=14, color="#ffffff", pad=15)
    ax.set_xlabel("Average Cost per Query (USD)", fontsize=13, color="#ffffff", labelpad=10)
    ax.set_ylabel("Accuracy (%)", fontsize=13, color="#ffffff", labelpad=10)

    # Set axes limits based on data
    all_costs = [d["cost"] for d in data.values()]
    all_accs = [d["accuracy"] for d in data.values()]

    min_cost = min(all_costs) if all_costs else 0.0
    max_cost = max(all_costs) if all_costs else 0.0006
    min_acc = min(all_accs) if all_accs else 50.0
    max_acc = max(all_accs) if all_accs else 65.0

    y_min = max(0.0, math.floor(min_acc / 5.0) * 5.0 - 5.0)
    y_max = min(100.0, math.ceil(max_acc / 5.0) * 5.0 + 8.0)

    ax.set_ylim(y_min, y_max)
    ax.set_xlim(-0.00003, max_cost * 1.15)

    # Format x-axis ticks with currency format
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"${x:.6f}"))
    ax.tick_params(axis="x", colors="#ffffff", labelsize=10)

    # Y-axis ticks
    ax.yaxis.set_major_locator(ticker.MultipleLocator(5))
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=100, decimals=0))
    ax.tick_params(axis="y", colors="#ffffff", labelsize=11)

    # Grid
    ax.grid(True, linestyle="-", color="#ffffff", alpha=0.2, zorder=1)

    # Spines
    for spine in ax.spines.values():
        spine.set_color("#71717a")
        spine.set_linewidth(1.0)

    # Legend
    legend = ax.legend(
        loc="upper left",
        frameon=True,
        facecolor="#0f172a",
        edgecolor="#475569",
        fontsize=11,
        labelcolor="#ffffff",
    )
    legend.get_frame().set_alpha(0.85)

    # Mock mode disclaimer note at the bottom
    fig.text(
        0.5,
        0.015,
        "Mock mode uses canned answers; it validates routing and cost accounting, not real accuracy.",
        ha="center",
        fontsize=9.5,
        color="#a1a1aa",
        fontstyle="italic",
    )

    plt.tight_layout(rect=[0, 0.03, 1, 1])
    plt.savefig(output_png, facecolor=fig.get_facecolor(), dpi=150)
    plt.close()
    print(f"Pareto chart successfully generated: {output_png}")


def main():
    parser = argparse.ArgumentParser(description="Generate CAAR Pareto frontier chart.")
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Input benchmark results (JSON or Markdown). Defaults to benchmark_results.json or BENCHMARK_REPORT.md",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="docs/pareto.png",
        help="Path to output PNG (default: docs/pareto.png)",
    )
    args = parser.parse_args()

    commit_hash = get_git_commit()

    # Determine input file
    input_file = args.input
    if not input_file:
        if os.path.exists("benchmark_results.json"):
            input_file = "benchmark_results.json"
        elif os.path.exists("BENCHMARK_REPORT.md"):
            input_file = "BENCHMARK_REPORT.md"
        else:
            print("Error: No benchmark results found. Run python run_benchmark.py first.")
            sys.exit(1)

    if input_file.endswith(".json"):
        data, total_items, date_str, mode_str = parse_from_json(input_file)
    else:
        data, total_items, date_str, mode_str = parse_from_markdown(input_file)

    if not data:
        print(f"Error: Could not parse benchmark data from {input_file}")
        sys.exit(1)

    build_pareto_chart(
        data=data,
        total_items=total_items,
        date_str=date_str,
        commit_hash=commit_hash,
        output_png=args.output,
        mode_str=mode_str,
    )


if __name__ == "__main__":
    main()
