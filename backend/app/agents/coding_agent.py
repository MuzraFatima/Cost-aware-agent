import time
import litellm
import ast
from typing import Dict, Any, List, Optional
from backend.app.agents.base import BaseAgent
from backend.app.core.config import settings
from backend.app.utils.cost_tracker import calculate_token_cost
from backend.app.agents._mock_answers import resolve as _mock_resolve
from backend.app.utils.llm_client import _push_keys, format_model_name

class CodingAgent(BaseAgent):
    """
    Specialized agent for software engineering, code generation, syntax checking,
    debugging, refactoring, and unit test writing.
    """

    def __init__(self, model: Optional[str] = None):
        super().__init__(name="Specialized Coding Agent", tier=3)
        self._model = model
        self.specialization = "coding"

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
        expected_format: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        start_time = time.time()

        system_instruction = (
            "You are a Senior Software Engineer and Code Synthesis Specialist. "
            "Write production-grade, clean, efficient code with type annotations, docstrings, "
            "and proper error handling. Enclose code in Markdown code blocks (e.g. ```python ... ```)."
        )

        formatted_messages = messages or []
        if not formatted_messages or formatted_messages[0].get("role") != "system":
            formatted_messages = [{"role": "system", "content": system_instruction}] + (messages or [{"role": "user", "content": prompt}])

        if getattr(self, "mock_mode", False) or settings.is_mock_mode:
            return self._execute_mock(prompt, expected_format or "python", start_time)

        try:
            _push_keys()
            target_model = format_model_name(self.model)
            response = await litellm.acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=0.2,
                max_tokens=900
            )

            choice = response.choices[0] if getattr(response, "choices", None) else None
            text = (choice.message.content if choice and hasattr(choice, "message") and hasattr(choice.message, "content") else "") or ""
            
            usage = getattr(response, "usage", None)
            tokens_in = getattr(usage, "prompt_tokens", 0) if usage else (len(prompt.split()) + 15)
            tokens_out = getattr(usage, "completion_tokens", 0) if usage else (len(text.split()) + 10)
            cost = calculate_token_cost(self.model, tokens_in, tokens_out)

            return {
                "text": text,
                "model_name": f"{self.model} (Coding)",
                "specialization": self.specialization,
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "cost": cost,
                "latency_ms": int((time.time() - start_time) * 1000),
                "tier": self.tier
            }
        except Exception as e:
            return self._execute_mock(prompt, expected_format or "python", start_time, error_msg=str(e))

    def _execute_mock(
        self,
        prompt: str,
        expected_format: Optional[str],
        start_time: float,
        error_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        time.sleep(0.5)
        text = _mock_resolve(prompt, expected_format="python", tier=self.tier)

        tokens_in = len(prompt.split()) + 10
        tokens_out = len(text.split()) + 10
        cost = calculate_token_cost(self.model, tokens_in, tokens_out)

        return {
            "text": text,
            "model_name": f"{self.model} (Coding - Simulated)",
            "specialization": self.specialization,
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost": cost,
            "latency_ms": int((time.time() - start_time) * 1000),
            "tier": self.tier
        }
