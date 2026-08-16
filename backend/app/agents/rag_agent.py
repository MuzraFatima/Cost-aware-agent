import time
import litellm
from typing import Dict, Any, List, Optional
from backend.app.agents.base import BaseAgent
from backend.app.core.config import settings
from backend.app.utils.cost_tracker import calculate_token_cost

MOCK_KNOWLEDGE_BASE = [
    {"keywords": ["pricing", "cost", "token"], "text": "CAAR systems reduce API billing by dynamically routing 65% of simple queries to commodity models, achieving up to 70% cost savings."},
    {"keywords": ["threshold", "confidence", "slider"], "text": "Routing thresholds are adjusted in real-time. Coding requires 0.85, General requires 0.65, and Math requires 0.85 by default."},
    {"keywords": ["developer", "creator", "team"], "text": "Cost-Aware Agent Router was designed by Advanced Agentic Coding team as a production-grade system design."},
]

class RAGAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Augmented RAG Agent", tier=2)
        self.model = settings.TIER_2_MODEL

    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        # 1. Retrieve relevant context
        context = self._retrieve_context(prompt)
        
        # 2. Augment prompt
        augmented_prompt = f"Context: {context}\n\nQuestion: {prompt}" if context else prompt
        formatted_messages = messages or [{"role": "user", "content": augmented_prompt}]
        
        # Mock mode
        if settings.OPENAI_API_KEY == "mock-openai-key":
            return self._execute_mock(prompt, context, expected_format, start_time)
            
        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=formatted_messages,
                temperature=0.4, # lower temperature for RAG QA stability
                max_tokens=600
            )
            
            text = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            cost = calculate_token_cost(self.model, tokens_in, tokens_out)
            
            return {
                "text": text,
                "model_name": f"{self.model} (RAG)",
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "cost": cost,
                "latency_ms": int((time.time() - start_time) * 1000),
                "tier": self.tier
            }
            
        except Exception as e:
            return self._execute_mock(prompt, context, expected_format, start_time, error_msg=str(e))

    def _retrieve_context(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        matched_contexts = []
        for item in MOCK_KNOWLEDGE_BASE:
            for kw in item["keywords"]:
                if kw in prompt_lower:
                    matched_contexts.append(item["text"])
                    break
        return " ".join(matched_contexts) if matched_contexts else "No context found in vector storage."

    def _execute_mock(
        self,
        prompt: str,
        context: str,
        expected_format: Optional[str],
        start_time: float,
        error_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        time.sleep(0.6) # Simulating context retrieval + cheap model latency
        
        # Generates a slightly better but still potentially low-confidence result
        if "pricing" in prompt.lower() or "cost" in prompt.lower():
            text = f"Based on retrieved documentation: {context} Thus, costs are minimized by up to 70%."
        elif "threshold" in prompt.lower():
            text = f"According to configuration keys: {context} These are stored dynamically in the policies database table."
        else:
            text = f"I found the following context: '{context}'. However, I cannot guarantee this directly answers your query: '{prompt}'."
            
        tokens_in = len(prompt.split()) + len(context.split()) + 10
        tokens_out = len(text.split()) + 5
        cost = calculate_token_cost(self.model, tokens_in, tokens_out)
        
        return {
            "text": text,
            "model_name": f"{self.model} + RAG (Simulated)",
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost": cost,
            "latency_ms": int((time.time() - start_time) * 1000),
            "tier": self.tier
        }
