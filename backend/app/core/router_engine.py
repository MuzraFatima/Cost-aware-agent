import time
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.confidence import ConfidenceEvaluator
from backend.app.db.models import RoutingPolicy, RoutingLog, RoutingStep
from backend.app.agents.cheap_agent import CheapAgent
from backend.app.agents.rag_agent import RAGAgent
from backend.app.agents.frontier_agent import FrontierAgent
from backend.app.agents.consensus_agent import ConsensusAgent
from backend.app.services.knowledge_base import KnowledgeBaseService
from backend.app.utils.cost_tracker import (

    estimate_frontier_cost,
    estimate_pre_request_cost,
    calculate_budget_status
)

class RouterEngine:
    def __init__(self, mock_mode: bool = False):
        # Initialize Agent pool
        self.agents = {
            1: CheapAgent(),
            2: RAGAgent(),
            3: FrontierAgent(),
            4: ConsensusAgent()
        }
        if mock_mode:
            for agent in self.agents.values():
                agent.mock_mode = True

    def classify_task_type(self, prompt: str, domain: Optional[str] = None) -> str:
        """
        Classifies prompt into one of 6 task categories:
        general, coding, math, research, analysis, creative.
        """
        import re
        prompt_lower = prompt.lower()

        simple_general_patterns = [
            r"^what is python\??$",
            r"^what is the capital of ",
            r"^explain what .* is",
            r"^hello", r"^hi\b",
            r"configuration json",
            r"config json"
        ]
        for pat in simple_general_patterns:
            if re.search(pat, prompt_lower):
                return "general"

        research_kw = [
            "multi-agent", "reinforcement learning", "architecture", "distributed system",
            "benchmark", "consensus verification", "comparative analysis", "tradeoff",
            "security audit", "high stakes", "system design"
        ]
        coding_patterns = [
            r"\bpython program\b", r"\bpython script\b", r"\bpython function\b",
            r"\bwrite a python\b", r"\bsort a list\b", r"\bdef \b", r"\bclass \b",
            r"\brefactor\b", r"\bsql\b", r"\balgorithm\b", r"\bdebug\b",
            r"\bwrite code\b", r"\bpython code\b"
        ]
        math_kw = [
            "derive", "integral", "theorem", "calculate", "equation", "proof",
            "probability", "matrix", "algebra", "calculus", "formula"
        ]
        analysis_kw = [
            "analyze", "data analysis", "log analysis", "trend", "metric", "dataset",
            "parse", "summary statistics"
        ]
        creative_kw = [
            "poem", "story", "essay", "brainstorm", "haiku", "creative writing", "tagline"
        ]

        if any(kw in prompt_lower for kw in research_kw):
            return "research"
        if any(re.search(pat, prompt_lower) for pat in coding_patterns):
            return "coding"
        if any(kw in prompt_lower for kw in math_kw):
            return "math"
        if any(kw in prompt_lower for kw in analysis_kw):
            return "analysis"
        if any(kw in prompt_lower for kw in creative_kw):
            return "creative"

        if domain and domain in ("coding", "math", "creative", "research", "analysis"):
            return domain

        return "general"


    def calculate_complexity_score(self, prompt: str, task_type: str) -> int:
        """
        Calculates a dynamic complexity score from 1 to 10 based on task type, keyword density,
        syntactic structure, and prompt length.
        """
        prompt_lower = prompt.lower()
        words = prompt.split()
        word_count = len(words)

        simple_indicators = ["what is ", "who is ", "define ", "hello", "hi", "what are ", "explain "]
        is_simple = any(prompt_lower.startswith(ind) for ind in simple_indicators) or (word_count <= 8 and not any(kw in prompt_lower for kw in ["sort a list", "multi-agent", "derive", "reinforcement"]))

        if is_simple and task_type == "general":
            return 2

        base_scores = {
            "general": 2,
            "creative": 3,
            "analysis": 5,
            "coding": 5,
            "math": 6,
            "research": 8
        }
        score = base_scores.get(task_type, 3)

        if any(kw in prompt_lower for kw in ["reinforcement learning", "multi-agent", "security audit", "consensus verification"]):
            score += 3
        elif any(kw in prompt_lower for kw in ["architecture", "system design", "distributed", "optimization"]):
            score += 2

        if word_count > 40:
            score += 2
        elif word_count > 20:
            score += 1

        if any(c in prompt for c in ["{", "}", "[", "]", "```"]):
            score += 1

        return max(1, min(10, score))


    def classify_complexity(self, prompt: str, domain: Optional[str] = None, db: Optional[Session] = None) -> int:
        """
        Determines starting tier (1-4) based on task category, vector similarity match, prompt keywords, and complexity score.
        """
        prompt_lower = prompt.lower()

        extreme_indicators = ["consensus verification", "bulletproof report", "high stakes", "audit", "security audit"]
        if any(ind in prompt_lower for ind in extreme_indicators):
            return 4

        task_type = self.classify_task_type(prompt, domain)
        complexity_score = self.calculate_complexity_score(prompt, task_type)

        # Cost-aware RAG check: Check if knowledge base contains relevant chunks (similarity >= 0.25)
        rag_indicators = ["pricing", "cost details", "threshold configurations", "developer team", "document", "knowledge base", "pdf"]
        has_kw_match = any(ind in prompt_lower for ind in rag_indicators)
        has_vector_match = False
        
        if db:
            try:
                top_chunks = KnowledgeBaseService.search_chunks(prompt, db=db, top_k=1, min_similarity=0.25)
                if top_chunks:
                    has_vector_match = True
            except Exception:
                pass

        if has_vector_match or has_kw_match:
            return 2

        if complexity_score <= 3:
            return 1
        elif complexity_score <= 6:
            return 3 if task_type in ("coding", "math") else 2
        elif complexity_score <= 8:
            return 3
        else:
            return 4


    def get_threshold(self, domain: str, db: Optional[Session] = None) -> float:
        """
        Retrieves threshold from DB if available, else returns the default.
        """
        if db:
            try:
                result = db.execute(
                    select(RoutingPolicy).where(RoutingPolicy.domain == domain)
                )
                policy = result.scalars().first()
                if policy:
                    return policy.min_confidence_threshold
            except Exception:
                pass # fallback
        return settings.DEFAULT_THRESHOLDS.get(domain, 0.70)

    async def route(
        self,
        prompt: str,
        domain: str = "general",
        expected_format: Optional[str] = None,
        db: Optional[Session] = None,
        budget_limit_usd: Optional[float] = None,
        messages: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Dynamically routes a prompt through the agent tiers based on confidence thresholds.
        Logs metrics and returns final output + path audit trace.
        """
        start_time = time.time()
        
        # 1. Get active confidence threshold & budget status
        threshold = self.get_threshold(domain, db)
        budget_status = calculate_budget_status(db=db)
        budget_pressure = budget_status["budget_pressure_score"]
        remaining_daily = budget_status["remaining_daily_budget_usd"]
        
        # 2. Determine task classification & ideal starting tier
        task_type = self.classify_task_type(prompt, domain)
        complexity_score = self.calculate_complexity_score(prompt, task_type)
        ideal_start_tier = self.classify_complexity(prompt, domain, db=db)
        
        # 3. Model selection & Pre-request cost estimation
        ideal_model_name = getattr(self.agents[ideal_start_tier], "model", settings.TIER_1_MODEL)
        pre_request_cost = estimate_pre_request_cost(ideal_model_name, prompt)
        
        # 4. Budget-aware model selection & Automatic Downgrade logic
        start_tier = ideal_start_tier
        downgrade_reasons = []

        # Rule A: Per-request budget cap enforcement
        if budget_limit_usd is not None and pre_request_cost > budget_limit_usd:
            if start_tier > 1:
                downgrade_reasons.append(
                    f"Est. cost (${pre_request_cost:.6f}) exceeds request budget limit (${budget_limit_usd:.6f})"
                )
                start_tier = 1

        # Rule B: Global budget pressure & daily budget cap enforcement
        if budget_pressure >= 95 or remaining_daily <= 0.0:
            if start_tier > 1:
                downgrade_reasons.append(
                    f"Critical budget pressure ({budget_pressure}/100, ${remaining_daily:.4f} remaining today)"
                )
                start_tier = 1
        elif budget_pressure >= 80:
            if start_tier >= 3:
                downgrade_reasons.append(
                    f"High budget pressure ({budget_pressure}/100, ${remaining_daily:.4f} remaining today)"
                )
                start_tier = 1 if complexity_score <= 7 else 2
        elif budget_pressure >= 50:
            if start_tier == 4 and complexity_score < 10:
                downgrade_reasons.append(
                    f"Moderate budget pressure ({budget_pressure}/100)"
                )
                start_tier = 3

        # 5. Execution cascade loop
        current_tier = start_tier
        steps_trace = []
        final_text = ""
        total_cost = 0.0
        sources = []
        rag_used = False
        retrieval_latency_ms = 0
        
        while current_tier <= 4:
            # Check budget constraints before attempting higher tiers in cascade
            if current_tier > start_tier:
                if budget_pressure >= 95:
                    print(f"[RouterEngine] Escalation stopped at Tier {current_tier} due to critical budget pressure ({budget_pressure}/100).")
                    break
                if budget_limit_usd is not None and total_cost >= budget_limit_usd:
                    print(f"[RouterEngine] Escalation stopped at Tier {current_tier}: budget limit ${budget_limit_usd:.6f} reached.")
                    break

            agent = self.agents[current_tier]
            
            try:
                # Execute current tier
                res = await agent.execute(prompt=prompt, messages=messages, expected_format=expected_format, db=db)
                
                # Check for RAG metadata in agent output
                if res.get("rag_used"):
                    rag_used = True
                    sources = res.get("sources", [])
                    retrieval_latency_ms = res.get("retrieval_latency_ms", 0)

                # Calculate confidence score
                confidence = await ConfidenceEvaluator.calculate_confidence(
                    prompt=prompt,
                    response_text=res["text"],
                    expected_format=expected_format,
                    use_judge=False # Set to True for production active grading
                )
                
                # Track steps
                step_record = {
                    "tier": current_tier,
                    "model_name": res["model_name"],
                    "confidence_score": confidence,
                    "tokens_input": res["tokens_input"],
                    "tokens_output": res["tokens_output"],
                    "cost": res["cost"],
                    "latency_ms": res["latency_ms"],
                    "rag_used": res.get("rag_used", False),
                    "sources": res.get("sources", []),
                    "retrieval_latency_ms": res.get("retrieval_latency_ms", 0)
                }
                steps_trace.append(step_record)
                
                total_cost += res["cost"]
                final_text = res["text"]
                
                # Check exit condition
                if confidence >= threshold:
                    break
            except Exception as e:
                # Handle agent execution failure gracefully:
                print(f"Error executing agent Tier {current_tier}: {e}")
                elapsed_so_far = sum(s["latency_ms"] for s in steps_trace)
                total_elapsed = int((time.time() - start_time) * 1000)
                step_latency = max(total_elapsed - elapsed_so_far, 0)
                
                step_record = {
                    "tier": current_tier,
                    "model_name": f"{agent.name} (FAILED)",
                    "confidence_score": 0.0,
                    "tokens_input": 0,
                    "tokens_output": 0,
                    "cost": 0.0,
                    "latency_ms": step_latency
                }
                steps_trace.append(step_record)
                
            current_tier += 1
            
        if not final_text:
            raise RuntimeError("All agent tiers failed to execute and generate a response.")
            
        # 6. Compute cost savings vs always-routing to Tier 3 (Frontier)
        total_tokens = sum(
            s.get("tokens_input", 0) + s.get("tokens_output", 0) for s in steps_trace
        )
        frontier_cost = estimate_frontier_cost(total_tokens)
        cost_savings = max(frontier_cost - total_cost, 0.0)

        selected_tier = steps_trace[-1]["tier"] if steps_trace else (current_tier if current_tier <= 4 else 4)
        selected_model = steps_trace[-1]["model_name"] if steps_trace else getattr(self.agents[selected_tier], "model", "groq/openai/gpt-oss-20b")

        # 7. Construct explainable routing_reason
        reason_parts = [
            f"Classified as '{task_type}' task (complexity {complexity_score}/10).",
            f"Budget pressure: {budget_pressure}/100."
        ]
        if rag_used and sources:
            reason_parts.append(f"Retrieved {len(sources)} knowledge base chunk(s).")
        if downgrade_reasons:
            reason_parts.append(
                f"Downgraded target Tier {ideal_start_tier} → Tier {start_tier} ({'; '.join(downgrade_reasons)})."
            )
        else:
            reason_parts.append(
                f"Initiated at Tier {start_tier} and resolved at Tier {selected_tier} ({selected_model})."
            )
        routing_reason = " ".join(reason_parts)

        # 8. Save audit log to database if session is present
        routing_log_id = None
        total_latency = int((time.time() - start_time) * 1000)
        
        if db:
            try:
                log_entry = RoutingLog(
                    prompt=prompt,
                    response=final_text,
                    total_cost=total_cost,
                    estimated_frontier_cost=round(frontier_cost, 8),
                    cost_savings=round(cost_savings, 8),
                    budget_limit_usd=budget_limit_usd,
                    total_latency_ms=total_latency,
                    final_tier=selected_tier
                )
                db.add(log_entry)
                db.flush()
                routing_log_id = log_entry.id
                
                for step in steps_trace:
                    step_entry = RoutingStep(
                        routing_log_id=routing_log_id,
                        tier=step["tier"],
                        model_name=step["model_name"],
                        confidence_score=step["confidence_score"],
                        tokens_input=step["tokens_input"],
                        tokens_output=step["tokens_output"],
                        cost=step["cost"],
                        latency_ms=step["latency_ms"]
                    )
                    db.add(step_entry)
                    
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Error logging route metrics: {e}")
                
        return {
            "id": routing_log_id,
            "text": final_text,
            "final_tier": selected_tier,
            "task_type": task_type,
            "complexity_score": complexity_score,
            "budget_pressure_score": budget_pressure,
            "remaining_daily_budget_usd": budget_status["remaining_daily_budget_usd"],
            "pre_request_estimated_cost_usd": pre_request_cost,
            "selected_model": selected_model,
            "routing_reason": routing_reason,
            "threshold_used": threshold,
            "rag_used": rag_used,
            "sources": sources,
            "retrieval_latency_ms": retrieval_latency_ms,
            "usage": {
                "total_cost_usd": round(total_cost, 8),
                "estimated_frontier_cost_usd": round(frontier_cost, 8),
                "cost_savings_usd": round(cost_savings, 8),
                "pre_request_estimated_cost_usd": pre_request_cost,
                "budget_pressure_score": budget_pressure,
                "remaining_daily_budget_usd": budget_status["remaining_daily_budget_usd"],
                "total_latency_ms": total_latency,
                "retrieval_latency_ms": retrieval_latency_ms,
                "rag_used": rag_used,
                "sources_count": len(sources),
                "routing_path": steps_trace,
                "budget_limit_usd": budget_limit_usd,
                "budget_exceeded": (
                    budget_limit_usd is not None and total_cost >= budget_limit_usd
                )
            }
        }


router_engine = RouterEngine()

