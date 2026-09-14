"""
evaluator.py
============
API endpoints for standalone answer evaluation, confidence breakdown,
and domain confidence calibration.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.answer_evaluator import AnswerEvaluator
from backend.app.core.confidence_calibration import ConfidenceCalibrationService
from backend.app.db.session import get_db

router = APIRouter()

class EvaluationRequest(BaseModel):
    prompt: str = Field(..., description="Original user prompt")
    response_text: str = Field(..., description="Candidate generation to evaluate")
    expected_format: Optional[str] = Field(None, description="Expected formatting (e.g. 'json', 'python')")
    domain: str = Field("general", description="Task domain for calibrated weighting (coding, math, rag, etc.)")
    task_type: str = Field("general", description="Specific task classification")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Retrieved RAG knowledge chunks for factuality check")
    threshold: Optional[float] = Field(None, description="Confidence threshold for acceptance verdict (default 0.70)")
    use_judge: bool = Field(False, description="Whether to invoke LLM-as-judge")

class CalibrationUpdateRequest(BaseModel):
    domain: str = Field(..., description="Domain name (e.g. 'coding', 'rag', 'general')")
    weights: Dict[str, float] = Field(..., description="Weight map (syntactic, semantic, hedging, factuality)")

@router.post("/evaluate")
async def evaluate_response(req: EvaluationRequest):
    """
    Evaluates a candidate answer across syntactic, semantic, hedging, and factuality dimensions.
    Returns calibrated confidence, verdict (ACCEPTED/ESCALATE), and constructive critique.
    """
    threshold = req.threshold if req.threshold is not None else 0.70
    result = await AnswerEvaluator.evaluate(
        prompt=req.prompt,
        response_text=req.response_text,
        expected_format=req.expected_format,
        domain=req.domain,
        task_type=req.task_type,
        sources=req.sources,
        threshold=threshold,
        use_judge=req.use_judge
    )
    return result

@router.get("/calibration")
def get_calibration_weights():
    """
    Returns active confidence calibration weight matrices across all domains.
    """
    return {
        "domain_weights": ConfidenceCalibrationService.get_all_weights()
    }

@router.put("/calibration")
def update_calibration_weights(req: CalibrationUpdateRequest):
    """
    Updates calibration weights for a specific domain.
    """
    try:
        updated = ConfidenceCalibrationService.update_domain_weights(req.domain, req.weights)
        return {
            "status": "success",
            "domain": req.domain,
            "normalized_weights": updated
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
