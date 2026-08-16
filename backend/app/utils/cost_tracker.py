import litellm
from typing import Dict, Any

# Local fallback pricing dictionary (Cost per token in USD)
FALLBACK_PRICING: Dict[str, Dict[str, float]] = {
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
    1: (0.15 + 0.60) / 2 / 1_000_000,    # gpt-4o-mini average
    2: (0.15 + 0.60) / 2 / 1_000_000,    # gpt-4o-mini + RAG overhead ≈ same base
    3: (5.00 + 15.00) / 2 / 1_000_000,   # gpt-4o average
    4: (5.00 + 15.00) / 2 / 1_000_000,   # gpt-4o consensus ≈ same
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
        # LiteLLM cost calculation logic
        input_cost, output_cost = litellm.get_max_logging_cost(
            model=model_name,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens
        )
        return float(input_cost + output_cost)
    except Exception:
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
        
    # Manual extraction if helper fail or mock object is passed
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

def estimate_frontier_cost(total_tokens: int, frontier_tier: int = 3) -> float:
    """
    Estimates what the request would have cost if always routed to the frontier (Tier 3)
    model. Used to calculate cost savings from the routing engine.

    Args:
        total_tokens: total tokens consumed across all steps (input + output combined).
        frontier_tier: the tier to use as the expensive baseline (default: 3).
    Returns:
        Estimated cost in USD at the frontier tier pricing.
    """
    cost_per_token = TIER_REFERENCE_COST_PER_TOKEN.get(frontier_tier, 10.00 / 1_000_000)
    return total_tokens * cost_per_token
