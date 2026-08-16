from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time

class BaseAgent(ABC):
    def __init__(self, name: str, tier: int):
        self.name = name
        self.tier = tier

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the agent workflow and returns a dictionary with:
        {
            "text": str,
            "model_name": str,
            "tokens_input": int,
            "tokens_output": int,
            "cost": float,
            "latency_ms": int,
            "tier": int
        }
        """
        pass
