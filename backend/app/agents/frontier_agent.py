import time
import litellm
import json
from typing import Dict, Any, List, Optional
from backend.app.agents.base import BaseAgent
from backend.app.core.config import settings
from backend.app.utils.cost_tracker import calculate_token_cost
from backend.app.agents._mock_answers import resolve as _mock_resolve
import backend.app.utils.llm_client  # propagates provider keys to LiteLLM at import time

class FrontierAgent(BaseAgent):
    def __init__(self, model: Optional[str] = None):
        super().__init__(name="Frontier Single Agent", tier=3)
        self._model = model

    @property
    def model(self) -> str:
        return self._model or settings.TIER_3_MODEL

    @model.setter
    def model(self, value: str):
        self._model = value

    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        formatted_messages = messages or [{"role": "user", "content": prompt}]
        
        # Mock mode — active when no real provider key is configured
        if settings.is_mock_mode:
            return self._execute_mock(prompt, expected_format, start_time)
            
        try:
            backend.app.utils.llm_client._push_keys()
            response = await litellm.acompletion(
                model=self.model,
                messages=formatted_messages,
                temperature=0.2, # low temperature for high precision
                max_tokens=1000
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
            return self._execute_mock(prompt, expected_format, start_time, error_msg=str(e))

    def _execute_mock(
        self,
        prompt: str,
        expected_format: Optional[str],
        start_time: float,
        error_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        time.sleep(1.2) # Frontier model latency simulation
        prompt_lower = prompt.lower()
        
        # Generates highly accurate, structured outputs with zero uncertainty keywords
        if "PII" in prompt or "pii" in prompt_lower:
            text = "I have detected requested identifiers. Per security policies, PII is redacted: [REDACTED_EMAIL], [REDACTED_PHONE]."
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
