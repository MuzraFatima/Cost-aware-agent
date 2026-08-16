# Cost-Aware Agent Router

A dynamic, confidence-based routing system that reduces LLM inference cost while maintaining response quality — routing tasks across multiple agents/models instead of relying on a single LLM for every request.

## Overview

Not every query needs the most expensive model. Cost-Aware Agent Router evaluates incoming tasks and routes each one to the most cost-effective model capable of handling it, using confidence scoring to decide when a cheaper/faster model is sufficient versus when a stronger model is warranted. This addresses a practical problem in production AI systems: LLM API costs scale directly with usage, and most requests don't need top-tier reasoning to be answered well.

**Research angle:** dynamic, confidence-based routing across multiple agents (rather than static routing to a single model) is a relatively unexplored area in multi-agent system design.

## Features

- **Confidence-based routing** — dynamically selects the model/agent best suited to a given task based on confidence scoring, rather than a fixed routing rule
- **Multi-model support** — works across multiple Groq-hosted models and open-source LLMs
- **Cost tracking** — measures dollar cost saved per routing decision compared to always using the top-tier model
- **Performance metrics** — tracks latency, accuracy, and token usage per request to evaluate routing quality
- **Evaluation-ready** — built with clear, measurable metrics (cost, latency, accuracy, tokens) for benchmarking routing strategies

## Tech stack

| Layer | Tech |
|---|---|
| Language | Python |
| Backend | FastAPI *(update if different)* |
| Storage | SQLite |
| LLM providers | Groq, open-source LLMs |
| Testing | pytest |

## Getting started

```bash
git clone https://github.com/MuzraFatima/Cost-aware-agent.git
cd Cost-aware-agent
pip install -r requirements.txt
python main.py
```

## Metrics tracked

- 💰 Cost saved ($) vs. single-model baseline
- ⚡ Latency per request
- 🎯 Accuracy / response quality
- 🔢 Token usage

## Why this approach

Static routing (always using one model, or simple rule-based fallbacks) leaves cost savings on the table. By scoring confidence dynamically per request, this router can send simple queries to cheaper/faster models and reserve stronger models for tasks that genuinely need them — cutting inference spend without sacrificing output quality.

## License

MIT
