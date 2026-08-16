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
from backend.app.utils.cost_tracker import estimate_frontier_cost

class RouterEngine:
    def __init__(self):
        # Initialize Agent pool
        self.agents = {
            1: CheapAgent(),
            2: RAGAgent(),
            3: FrontierAgent(),
            4: ConsensusAgent()
        }

    def classify_complexity(self, prompt: str, domain: Optional[str] = None) -> int:
        """
        Runs simple pre-routing check to determine starting tier based on prompt keywords and domain.
        Avoids cascading latency for queries that are clearly complex.
        """
        prompt_lower = prompt.lower()
        
        # Look for indicators of complex math or coding
        math_indicators = ["derive", "integral", "theorem", "calculate the probability", "solve equation"]
        coding_indicators = ["write a python script", "class interface", "refactor this code", "sql query for", "json schema"]
        extreme_indicators = ["consensus verification", "bulletproof report", "high stakes", "audit", "security audit"]
        
        # Check extreme first -> Tier 4
        if any(ind in prompt_lower for ind in extreme_indicators):
            return 4
        # Check coding/math -> Tier 3
        if any(ind in prompt_lower for ind in math_indicators) or any(ind in prompt_lower for ind in coding_indicators):
            return 3
        # Check domain lookup hints -> Tier 2
        rag_indicators = ["pricing", "cost details", "threshold configurations", "developer team"]
        if any(ind in prompt_lower for ind in rag_indicators):
            return 2
            
        # If no keywords match, use explicit domain parameter to help select starting tier
        if domain == "coding" or domain == "math":
            return 3
        elif domain == "creative":
            return 1
            
        # Defaults to Tier 1
        return 1

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
        budget_limit_usd: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Dynamically routes a prompt through the agent tiers based on confidence thresholds.
        Logs metrics and returns final output + path audit trace.
        """
        start_time = time.time()
        
        # 1. Get active confidence threshold
        threshold = self.get_threshold(domain, db)
        
        # 2. Determine starting tier
        start_tier = self.classify_complexity(prompt, domain)
        
        # 3. Execution cascade loop
        current_tier = start_tier
        steps_trace = []
        final_text = ""
        total_cost = 0.0
        
        while current_tier <= 4:
            agent = self.agents[current_tier]
            
            try:
                # Execute current tier
                res = await agent.execute(prompt=prompt, expected_format=expected_format)
                
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
                    "latency_ms": res["latency_ms"]
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
                # Record the failed step with 0 confidence, 0 cost, and estimated latency
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
                
            # If confidence is too low or agent execution failed, escalate to next tier
            # Budget guard: stop escalating if the next tier would exceed the per-request limit
            if budget_limit_usd is not None and total_cost >= budget_limit_usd:
                print(f"[RouterEngine] Budget limit ${budget_limit_usd:.5f} reached after Tier {current_tier}. Stopping escalation.")
                break
            current_tier += 1
            
        if not final_text:
            raise RuntimeError("All agent tiers failed to execute and generate a response.")
            
        # 4. Compute cost savings vs always-routing to Tier 3 (Frontier)
        total_tokens = sum(
            s.get("tokens_input", 0) + s.get("tokens_output", 0) for s in steps_trace
        )
        frontier_cost = estimate_frontier_cost(total_tokens)
        cost_savings = max(frontier_cost - total_cost, 0.0)

        # 5. Save audit log to database if session is present
        routing_log_id = None
        total_latency = int((time.time() - start_time) * 1000)
        
        if db:
            try:
                # Create routing log entry
                log_entry = RoutingLog(
                    prompt=prompt,
                    response=final_text,
                    total_cost=total_cost,
                    estimated_frontier_cost=round(frontier_cost, 8),
                    cost_savings=round(cost_savings, 8),
                    budget_limit_usd=budget_limit_usd,
                    total_latency_ms=total_latency,
                    final_tier=current_tier if current_tier <= 4 else 4
                )
                db.add(log_entry)
                db.flush() # populates log_entry.id
                routing_log_id = log_entry.id
                
                # Create step records
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
            "final_tier": current_tier if current_tier <= 4 else 4,
            "threshold_used": threshold,
            "usage": {
                "total_cost_usd": round(total_cost, 8),
                "estimated_frontier_cost_usd": round(frontier_cost, 8),
                "cost_savings_usd": round(cost_savings, 8),
                "total_latency_ms": total_latency,
                "routing_path": steps_trace,
                "budget_limit_usd": budget_limit_usd,
                "budget_exceeded": (
                    budget_limit_usd is not None and total_cost >= budget_limit_usd
                )
            }
        }

router_engine = RouterEngine()
