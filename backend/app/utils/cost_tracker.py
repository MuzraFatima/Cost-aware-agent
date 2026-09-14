import litellm
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.models import RoutingLog, BudgetConfig

# Local fallback pricing dictionary (Cost per token in USD)
FALLBACK_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-oss-20b": {
        "input": 0.10 / 1_000_000,
        "output": 0.40 / 1_000_000,
    },
    "gpt-oss-120b": {
        "input": 0.60 / 1_000_000,
        "output": 2.40 / 1_000_000,
    },
    "gpt-4o-mini": {
        "input": 0.15 / 1_000_000,
        "output": 0.60 / 1_000_000,
    },
    "gpt-4o": {
        "input": 5.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    "claude-3-5-sonnet": {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    "claude-3-haiku": {
        "input": 0.25 / 1_000_000,
        "output": 1.25 / 1_000_000,
    },
    "mock-cheap": {
        "input": 0.10 / 1_000_000,
        "output": 0.40 / 1_000_000,
    },
    "mock-expensive": {
        "input": 10.00 / 1_000_000,
        "output": 30.00 / 1_000_000,
    }
}

# Reference cost per token (USD) for each tier — used for savings calculation.
# Tier 3 (Frontier) is the "always-expensive" baseline to compare against.
TIER_REFERENCE_COST_PER_TOKEN: Dict[int, float] = {
    1: (0.10 + 0.40) / 2 / 1_000_000,    # gpt-oss-20b average
    2: (0.10 + 0.40) / 2 / 1_000_000,    # gpt-oss-20b + RAG overhead
    3: (0.60 + 2.40) / 2 / 1_000_000,    # gpt-oss-120b average
    4: (0.60 + 2.40) / 2 / 1_000_000,    # gpt-oss-120b consensus average
}

def calculate_token_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculates cost based on token counts. Checks fallback pricing if model not recognized.
    """
    clean_model = model_name.split("/")[-1].lower() # strip provider prefix (e.g. openai/gpt-4o -> gpt-4o)
    
    # Try custom/fallback pricing dictionary first
    for model_key, prices in FALLBACK_PRICING.items():
        if model_key in clean_model:
            return (input_tokens * prices["input"]) + (output_tokens * prices["output"])
            
    # LiteLLM cost lookup fallback if not in local map
    try:
        input_cost, output_cost = litellm.cost_per_token(
            model=model_name,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens
        )
        total = float(input_cost) + float(output_cost)
        if total >= 0.0:
            return total
    except Exception:
        pass
    # Return a conservative estimate if lookup fails entirely
    return (input_tokens * (1.0 / 1_000_000)) + (output_tokens * (5.0 / 1_000_000))

def get_response_cost(response_obj: Any) -> float:
    """
    Estimates cost from a LiteLLM response object.
    """
    try:
        cost = litellm.completion_cost(response_obj)
        if cost and cost > 0.0:
            return float(cost)
    except Exception:
        pass
        
    try:
        model = response_obj.model
        usage = response_obj.usage
        return calculate_token_cost(
            model_name=model,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens
        )
    except Exception:
        return 0.0

def estimate_tokens(prompt: str) -> int:
    """Estimates number of tokens in prompt text."""
    if not prompt:
        return 0
    words = len(prompt.split())
    return max(1, int(words * 1.35) + 5)

def estimate_pre_request_cost(
    model_name: str,
    prompt_text: str,
    expected_output_tokens: int = 400
) -> float:
    """
    Calculates estimated USD cost for calling model_name given prompt_text.
    Handles single models or Consensus Loop multi-call estimations.
    """
    input_tokens = estimate_tokens(prompt_text)
    
    clean_model = model_name.lower()
    if "consensus" in clean_model:
        # Consensus loop executes candidate models (20b + 120b) + synthesis
        c1 = calculate_token_cost(settings.TIER_1_MODEL, input_tokens, expected_output_tokens)
        c2 = calculate_token_cost(settings.TIER_3_MODEL, input_tokens, expected_output_tokens)
        synth = calculate_token_cost(settings.TIER_3_MODEL, input_tokens + (expected_output_tokens * 2), expected_output_tokens)
        return round(c1 + c2 + synth, 6)

    return round(calculate_token_cost(model_name, input_tokens, expected_output_tokens), 6)

def estimate_frontier_cost(total_tokens: int, frontier_tier: int = 3) -> float:
    """
    Estimates what the request would have cost if always routed to the frontier (Tier 3)
    model. Used to calculate cost savings from the routing engine.
    """
    cost_per_token = TIER_REFERENCE_COST_PER_TOKEN.get(frontier_tier, (0.60 + 2.40) / 2 / 1_000_000)
    return total_tokens * cost_per_token

def calculate_budget_status(
    db: Optional[Session] = None,
    daily_limit: Optional[float] = None,
    monthly_limit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculates current spend today, spend this month, remaining budgets,
    and dynamic budget pressure score (0-100).
    """
    d_limit = daily_limit if daily_limit is not None else getattr(settings, "DAILY_BUDGET_USD", 10.0)
    m_limit = monthly_limit if monthly_limit is not None else getattr(settings, "MONTHLY_BUDGET_USD", 100.0)
    
    if db:
        try:
            cfg = db.execute(select(BudgetConfig)).scalars().first()
            if cfg:
                if daily_limit is None:
                    d_limit = cfg.daily_budget_usd
                if monthly_limit is None:
                    m_limit = cfg.monthly_budget_usd
        except Exception:
            pass

    daily_spent = 0.0
    monthly_spent = 0.0
    total_spent = 0.0
    total_requests = 0

    if db:
        try:
            now = datetime.now(timezone.utc)
            start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

            # Daily spent
            d_res = db.execute(
                select(func.sum(RoutingLog.total_cost)).where(RoutingLog.created_at >= start_of_day)
            ).scalar()
            daily_spent = float(d_res or 0.0)

            # Monthly spent
            m_res = db.execute(
                select(func.sum(RoutingLog.total_cost)).where(RoutingLog.created_at >= start_of_month)
            ).scalar()
            monthly_spent = float(m_res or 0.0)

            # Total spent & requests
            t_res = db.execute(
                select(func.sum(RoutingLog.total_cost), func.count(RoutingLog.id))
            ).first()
            if t_res:
                total_spent = float(t_res[0] or 0.0)
                total_requests = int(t_res[1] or 0)
        except Exception:
            pass

    remaining_daily = max(0.0, d_limit - daily_spent)
    remaining_monthly = max(0.0, m_limit - monthly_spent)

    daily_ratio = (daily_spent / d_limit) if d_limit > 0 else 0.0
    monthly_ratio = (monthly_spent / m_limit) if m_limit > 0 else 0.0
    budget_pressure = min(100, int(round(max(daily_ratio, monthly_ratio) * 100)))

    avg_cost = (total_spent / total_requests) if total_requests > 0 else 0.0

    return {
        "daily_budget_usd": round(d_limit, 4),
        "monthly_budget_usd": round(m_limit, 4),
        "daily_spent_usd": round(daily_spent, 6),
        "monthly_spent_usd": round(monthly_spent, 6),
        "remaining_daily_budget_usd": round(remaining_daily, 6),
        "remaining_monthly_budget_usd": round(remaining_monthly, 6),
        "budget_pressure_score": budget_pressure,
        "avg_cost_per_request_usd": round(avg_cost, 6),
        "total_spent_usd": round(total_spent, 6),
        "total_requests": total_requests
    }
