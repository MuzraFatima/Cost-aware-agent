import time
import litellm
from typing import Dict, Any, List, Optional
from backend.app.agents.base import BaseAgent
from backend.app.core.config import settings
from backend.app.utils.cost_tracker import calculate_token_cost
from backend.app.agents._mock_answers import resolve as _mock_resolve
from backend.app.utils.llm_client import _push_keys, format_model_name

class CheapAgent(BaseAgent):
    def __init__(self, model: Optional[str] = None):
        super().__init__(name="Cheap Direct Agent", tier=1)
        self._model = model

    @property
    def model(self) -> str:
        return self._model or settings.TIER_1_MODEL

    @model.setter
    def model(self, value: str):
        self._model = value

    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        # Prepare messages
        formatted_messages = messages or [{"role": "user", "content": prompt}]
        
        # Mock mode — active when no real provider key is configured or explicitly enabled
        if getattr(self, "mock_mode", False) or settings.is_mock_mode:
            return self._execute_mock(prompt, expected_format, start_time)
            
        try:
            _push_keys()
            target_model = format_model_name(self.model)
            response = await litellm.acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=0.7,
                max_tokens=500
            )

            
            choice = response.choices[0] if getattr(response, "choices", None) else None
            text = (choice.message.content if choice and hasattr(choice, "message") and hasattr(choice.message, "content") else "") or ""
            usage = getattr(response, "usage", None)
            tokens_in = getattr(usage, "prompt_tokens", 0) if usage else (len(prompt.split()) + 5)
            tokens_out = getattr(usage, "completion_tokens", 0) if usage else (len(text.split()) + 5)
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

        if expected_format == "json":
            # Tier 1 (cheap/fast) cannot reliably produce valid structured JSON.
            # Return deliberately malformed JSON so ConfidenceEvaluator fails
            # syntactic validation -> confidence drops below threshold -> RouterEngine
            # escalates to a higher tier that can properly format JSON output.
            text = '{ "status": "incomplete", "message": "Demo'  # truncated, invalid JSON
        else:
            text = _mock_resolve(prompt, expected_format, tier=self.tier)
        
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
