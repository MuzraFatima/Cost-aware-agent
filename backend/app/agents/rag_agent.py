import time
import litellm
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.agents.base import BaseAgent
from backend.app.core.config import settings
from backend.app.utils.cost_tracker import calculate_token_cost
from backend.app.agents._mock_answers import resolve as _mock_resolve
from backend.app.utils.llm_client import _push_keys, format_model_name
from backend.app.services.knowledge_base import KnowledgeBaseService

MOCK_KNOWLEDGE_BASE = [
    {"keywords": ["pricing", "cost", "token"], "filename": "CAAR_Pricing_Guide.md", "text": "CAAR systems reduce API billing by dynamically routing 65% of simple queries to commodity models, achieving up to 70% cost savings."},
    {"keywords": ["threshold", "confidence", "slider"], "filename": "Routing_Policy_Spec.md", "text": "Routing thresholds are adjusted in real-time. Coding requires 0.85, General requires 0.65, and Math requires 0.85 by default."},
    {"keywords": ["developer", "creator", "team"], "filename": "Architecture_Overview.md", "text": "Cost-Aware Agent Router was designed by Advanced Agentic Coding team as a production-grade system design."},
]

class RAGAgent(BaseAgent):

    def __init__(self, model: Optional[str] = None):
        super().__init__(name="Augmented RAG Agent", tier=2)
        self._model = model

    @property
    def model(self) -> str:
        return self._model or settings.TIER_2_MODEL

    @model.setter
    def model(self, value: str):
        self._model = value

    async def execute(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        retrieval_start = time.time()
        
        # 1. Retrieve dynamic vector context from KnowledgeBaseService or mock KB fallback
        db_sources = KnowledgeBaseService.search_chunks(prompt, db=db, top_k=3, min_similarity=0.15) if db else []
        retrieval_ms = int((time.time() - retrieval_start) * 1000)
        
        sources = []
        context_parts = []
        
        if db_sources:
            for s in db_sources:
                sources.append({
                    "document_name": s["document_name"],
                    "chunk_id": s["chunk_id"],
                    "chunk_index": s["chunk_index"],
                    "similarity_score": s["similarity_score"],
                    "text_snippet": s["text_snippet"]
                })
                context_parts.append(f"[Document: {s['document_name']}, Chunk #{s['chunk_index']}] {s['text_snippet']}")
        else:
            # Fallback to static pre-seeded knowledge base
            prompt_lower = prompt.lower()
            for item in MOCK_KNOWLEDGE_BASE:
                for kw in item["keywords"]:
                    if kw in prompt_lower:
                        context_parts.append(f"[Document: {item['filename']}] {item['text']}")
                        sources.append({
                            "document_name": item["filename"],
                            "chunk_id": f"mock-{kw}",
                            "chunk_index": 0,
                            "similarity_score": 0.85,
                            "text_snippet": item["text"]
                        })
                        break

        context_str = "\n\n".join(context_parts) if context_parts else ""
        rag_used = bool(context_parts)

        # 2. Augment prompt with context
        augmented_prompt = f"Context:\n{context_str}\n\nQuestion: {prompt}\n\nAnswer using context and include source citations where applicable." if context_str else prompt
        formatted_messages = messages or [{"role": "user", "content": augmented_prompt}]
        
        # Mock mode execution
        if getattr(self, "mock_mode", False) or settings.is_mock_mode:
            return self._execute_mock(prompt, context_str, sources, expected_format, start_time, retrieval_ms, rag_used)
            
        try:
            _push_keys()
            target_model = format_model_name(self.model)
            response = await litellm.acompletion(
                model=target_model,
                messages=formatted_messages,
                temperature=0.3, # lower temperature for stable RAG responses
                max_tokens=650
            )

            choice = response.choices[0] if getattr(response, "choices", None) else None
            raw_text = (choice.message.content if choice and hasattr(choice, "message") and hasattr(choice.message, "content") else "") or ""
            
            # Append source citations if not present in raw output
            final_text = self._append_citations(raw_text, sources)

            usage = getattr(response, "usage", None)
            tokens_in = getattr(usage, "prompt_tokens", 0) if usage else (len(augmented_prompt.split()) + 5)
            tokens_out = getattr(usage, "completion_tokens", 0) if usage else (len(final_text.split()) + 5)
            cost = calculate_token_cost(self.model, tokens_in, tokens_out)
            
            return {
                "text": final_text,
                "model_name": f"{self.model} (RAG)",
                "tokens_input": tokens_in,
                "tokens_output": tokens_out,
                "cost": cost,
                "latency_ms": int((time.time() - start_time) * 1000),
                "retrieval_latency_ms": retrieval_ms,
                "tier": self.tier,
                "sources": sources,
                "rag_used": rag_used
            }
            
        except Exception as e:
            return self._execute_mock(prompt, context_str, sources, expected_format, start_time, retrieval_ms, rag_used, error_msg=str(e))

    def _append_citations(self, text: str, sources: List[Dict[str, Any]]) -> str:
        if not sources:
            return text
        if "Sources:" in text or "Source:" in text:
            return text
            
        citation_lines = ["\n\nSources:"]
        seen_docs = set()
        for s in sources:
            doc_name = s.get("document_name", "Document")
            if doc_name not in seen_docs:
                score = s.get("similarity_score", 0.0)
                citation_lines.append(f"- {doc_name} (Relevance: {score:.2f})")
                seen_docs.add(doc_name)
                
        return text + "\n".join(citation_lines)

    def _execute_mock(
        self,
        prompt: str,
        context: str,
        sources: List[Dict[str, Any]],
        expected_format: Optional[str],
        start_time: float,
        retrieval_ms: int,
        rag_used: bool,
        error_msg: Optional[str] = None
    ) -> Dict[str, Any]:
        time.sleep(0.4) # Simulating context retrieval + model execution
        
        if "pricing" in prompt.lower() or "cost" in prompt.lower():
            raw_text = f"Based on retrieved documentation, CAAR reduces API costs by up to 70% by routing queries dynamically."
        elif "threshold" in prompt.lower():
            raw_text = f"According to knowledge base specs, default routing thresholds are 0.85 for coding/math and 0.65 for general queries."
        else:
            kb_answer = _mock_resolve(prompt, expected_format, tier=self.tier)
            if context:
                raw_text = f"Based on retrieved context:\n{kb_answer}"
            else:
                raw_text = kb_answer
                
        final_text = self._append_citations(raw_text, sources)
            
        tokens_in = len(prompt.split()) + len(context.split()) + 15
        tokens_out = len(final_text.split()) + 5
        cost = calculate_token_cost(self.model, tokens_in, tokens_out)
        
        return {
            "text": final_text,
            "model_name": f"{self.model} + RAG (Simulated)",
            "tokens_input": tokens_in,
            "tokens_output": tokens_out,
            "cost": cost,
            "latency_ms": int((time.time() - start_time) * 1000),
            "retrieval_latency_ms": retrieval_ms,
            "tier": self.tier,
            "sources": sources,
            "rag_used": rag_used
        }
