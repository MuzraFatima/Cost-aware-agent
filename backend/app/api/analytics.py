from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Dict, Any, List

from backend.app.db.session import get_db
from backend.app.db.models import RoutingLog, RoutingStep

router = APIRouter()

@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Retrieves aggregated performance, cost, and routing efficiency statistics.
    """
    # 1. Total Requests
    total_res = db.execute(select(func.count(RoutingLog.id)))
    total_requests = total_res.scalar() or 0
    
    if total_requests == 0:
        return {
            "total_requests": 0,
            "total_cost_spent": 0.00,
            "total_estimated_frontier_cost": 0.00,
            "cost_saved_vs_frontier_only": 0.00,
            "average_latency_ms": 0,
            "average_confidence": 0.00,
            "tier_distribution": {
                "tier_1": 0.0,
                "tier_2": 0.0,
                "tier_3": 0.0,
                "tier_4": 0.0
            }
        }
        
    # 2. Total Cost, Frontier Cost, Cost Savings, Latency
    summary_res = db.execute(
        select(
            func.sum(RoutingLog.total_cost),
            func.sum(RoutingLog.estimated_frontier_cost),
            func.sum(RoutingLog.cost_savings),
            func.avg(RoutingLog.total_latency_ms)
        )
    )
    total_cost, total_frontier_cost, total_savings, avg_latency = summary_res.first()
    total_cost = float(total_cost or 0.0)
    total_frontier_cost = float(total_frontier_cost or 0.0)
    total_savings = float(total_savings or 0.0)
    avg_latency = int(avg_latency or 0)
    
    # 3. Calculate Average Confidence of final steps
    conf_res = db.execute(
        select(func.avg(RoutingStep.confidence_score))
    )
    avg_confidence = float(conf_res.scalar() or 0.0)
    
    # 4. Count of runs per final tier
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for t in [1, 2, 3, 4]:
        res = db.execute(
            select(func.count(RoutingLog.id)).where(RoutingLog.final_tier == t)
        )
        tier_counts[t] = res.scalar() or 0
        
    tier_dist = {
        f"tier_{t}": round(tier_counts[t] / total_requests, 2) if total_requests > 0 else 0.0
        for t in [1, 2, 3, 4]
    }
    
    return {
        "total_requests": total_requests,
        "total_cost_spent": round(total_cost, 6),
        "total_estimated_frontier_cost": round(total_frontier_cost, 6),
        "cost_saved_vs_frontier_only": round(total_savings, 6),
        "average_latency_ms": avg_latency,
        "average_confidence": round(avg_confidence, 2),
        "tier_distribution": tier_dist
    }

@router.get("/logs")
def get_recent_logs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Returns lists of recent query records, execution steps, cost, and latency traces.
    """
    result = db.execute(
        select(RoutingLog)
        .order_by(RoutingLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()
    
    log_list = []
    for log in logs:
        steps = []
        for step in log.steps:
            steps.append({
                "tier": step.tier,
                "model_name": step.model_name,
                "confidence_score": step.confidence_score,
                "tokens_input": step.tokens_input,
                "tokens_output": step.tokens_output,
                "cost": step.cost,
                "latency_ms": step.latency_ms
            })
            
        log_list.append({
            "id": log.id,
            "prompt": log.prompt,
            "response": log.response,
            "total_cost": log.total_cost,
            "total_latency_ms": log.total_latency_ms,
            "final_tier": log.final_tier,
            "eval_score": log.eval_score,
            "feedback_text": log.feedback_text,
            "created_at": log.created_at.isoformat(),
            "steps": steps
        })
        
    return log_list
