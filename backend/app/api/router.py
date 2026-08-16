from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Dict, Any, Optional

from backend.app.db.session import get_db
from backend.app.db.models import RoutingLog, RoutingPolicy
from backend.app.core.router_engine import router_engine

router = APIRouter()

class CompletionRequest(BaseModel):
    prompt: str = Field(..., description="The user query prompt")
    domain: str = Field("general", description="The query domain (e.g. coding, math, general, creative)")
    expected_format: Optional[str] = Field(None, description="Expected response format (e.g. 'json', 'python')")
    budget_limit_usd: Optional[float] = Field(
        None,
        ge=0.0,
        description="Optional per-request budget cap in USD. Routing stops escalating once this cost is reached."
    )

class FeedbackRequest(BaseModel):
    routing_log_id: str = Field(..., description="ID of the completed routing log")
    score: float = Field(..., ge=0.0, le=1.0, description="Feedback evaluation score (0.0 = bad, 1.0 = good)")
    feedback_text: Optional[str] = Field(None, description="Optional text context")

@router.post("/completions")
async def create_completion(
    request: CompletionRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluates prompt complexity, runs agent cascade based on confidence thresholds,
    records execution paths, and outputs response.
    """
    if not request.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prompt cannot be empty"
        )
        
    try:
        result = await router_engine.route(
            prompt=request.prompt,
            domain=request.domain,
            expected_format=request.expected_format,
            db=db,
            budget_limit_usd=request.budget_limit_usd
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Routing execution failed: {str(e)}"
        )

@router.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Saves user/evaluator feedback and adjusts confidence thresholds.
    """
    # 1. Look up log record
    result = db.execute(select(RoutingLog).where(RoutingLog.id == request.routing_log_id))
    log_record = result.scalars().first()
    
    if not log_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Routing log not found"
        )
        
    # 2. Update feedback info
    log_record.eval_score = request.score
    log_record.feedback_text = request.feedback_text
    
    # 3. Policy Optimization Loop (Contextual Threshold Adapter)
    prompt_lower = log_record.prompt.lower()
    domain = "general"
    if "code" in prompt_lower or "python" in prompt_lower or "def " in prompt_lower:
        domain = "coding"
    elif "math" in prompt_lower or "solve" in prompt_lower or "calculate" in prompt_lower:
        domain = "math"
    elif "write" in prompt_lower or "poem" in prompt_lower or "essay" in prompt_lower:
        domain = "creative"
        
    policy_result = db.execute(select(RoutingPolicy).where(RoutingPolicy.domain == domain))
    policy = policy_result.scalars().first()
    
    if policy:
        old_threshold = policy.min_confidence_threshold
        if request.score < 0.5:
            # Increase threshold (penalty step)
            new_threshold = min(old_threshold + 0.05, 0.95)
        else:
            # Decrease threshold (exploration step)
            new_threshold = max(old_threshold - 0.01, 0.40)
            
        policy.min_confidence_threshold = round(new_threshold, 2)
        db.flush()
        
    db.commit()
    
    return {
        "status": "success",
        "message": "Feedback submitted, routing policy adapted",
        "domain_adapted": domain,
        "new_threshold": policy.min_confidence_threshold if policy else None
    }
