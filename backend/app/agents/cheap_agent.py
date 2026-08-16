import time
import litellm
import re
from typing import Dict, Any, List, Optional
from backend.app.agents.base import BaseAgent
from backend.app.core.config import settings
from backend.app.utils.cost_tracker import calculate_token_cost

# Simple demo knowledge base for deterministic answers
_DEMO_KB = {
    "capital of india": "New Delhi",
    "capital of france": "Paris",
    "capital of spain": "Madrid",
    "capital of germany": "Berlin",
    "capital of japan": "Tokyo",
    "capital of australia": "Canberra",
    "capital of canada": "Ottawa",
    "capital of china": "Beijing",
    "capital of brazil": "Brasília",
    "capital of united states": "Washington, D.C.",
}

def _simple_math_evaluate(expr: str) -> str:
    """Safely evaluate simple arithmetic expressions like '123 * 45' or '12 + 34'"""
    # Allow only numbers and basic operators
    if not re.fullmatch(r"[0-9\s\+\-\*/]+", expr):
        return "Unable to compute the expression."
    try:
        result = eval(expr, {"__builtins__": {}}, {})
        return str(result)
    except Exception:
        return "Unable to compute the expression."

class CheapAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Cheap Direct Agent", tier=1)
        self.model = settings.TIER_1_MODEL

    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        # Prepare messages
        formatted_messages = messages or [{"role": "user", "content": prompt}]
        
        # Mock mode
        if settings.OPENAI_API_KEY == "mock-openai-key":
            return self._execute_mock(prompt, expected_format, start_time)
            
        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=formatted_messages,
                temperature=0.7,
                max_tokens=500
            )
            
            text = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            cost = calculate_token_cost(self.model, tokens_in, tokens_out)
            
            return {
                "text": text,
                "model_name": self.model,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "cost": cost,
                "latency_ms": int((time.time() - start_time) * 1000),
                "tier": self.tier
            }
            
        except Exception as e:
            # Fallback to mock on any error (including LiteLLM errors)
            return self._execute_mock(prompt, expected_format, start_time, error_msg=str(e))

    def _execute_mock(
        self,
        prompt: str,
        expected_format: Optional[str],
        start_time: float,
        error_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        # Simulate latency
        time.sleep(0.4)
        prompt_lower = prompt.lower().strip()
        
        # Try to answer capital questions
        capital_match = re.search(r"capital of ([a-z \-']+)", prompt_lower)
        if capital_match:
            country = capital_match.group(1).strip()
            answer = _DEMO_KB.get(f"capital of {country}")
            if answer:
                text = f"The capital of {country.title()} is {answer}."
            else:
                text = f"I do not have the capital information for {country.title()}."
        # Simple arithmetic detection
        elif any(op in prompt_lower for op in ["+", "-", "*", "/"]):
            # Extract the expression after the word 'calculate' or just the whole prompt
            expr = re.findall(r"([0-9\s\+\-\*/]+)", prompt)
            if expr:
                result = _simple_math_evaluate(expr[0])
                text = f"The result of {expr[0].strip()} is {result}."
            else:
                text = "I could not identify an arithmetic expression to compute."
        elif expected_format == "json":
            # Tier 1 (cheap/fast) cannot reliably produce valid structured JSON.
            # Return deliberately malformed JSON so ConfidenceEvaluator fails
            # syntactic validation -> confidence drops below threshold -> RouterEngine
            # escalates to a higher tier that can properly format JSON output.
            text = '{ "status": "incomplete", "message": "Demo'  # truncated, invalid JSON
        elif "json" in prompt_lower:
            # Prompt mentions JSON but no strict format required - return prose
            text = f"Answer: {prompt} (demo response)"
        else:
            # Generic fallback that echoes the request with a deterministic phrase
            text = f"Answer: {prompt} (demo response)"
        
        tokens_in = len(prompt.split()) + 5
        tokens_out = len(text.split()) + 5
        cost = calculate_token_cost(self.model, tokens_in, tokens_out)
        
        return {
            "text": text,
            "model_name": f"{self.model} (Simulated)",
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost": cost,
            "latency_ms": int((time.time() - start_time) * 1000),
            "tier": self.tier
        }
