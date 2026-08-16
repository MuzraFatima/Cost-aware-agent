from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List

from backend.app.db.session import get_db
from backend.app.db.models import RoutingPolicy

router = APIRouter()

class PolicyUpdateRequest(BaseModel):
    domain: str = Field(..., description="The query domain target")
    min_confidence_threshold: float = Field(..., ge=0.0, le=1.0, description="The minimum confidence value")

class PolicySchema(BaseModel):
    domain: str
    min_confidence_threshold: float
    
    class Config:
        from_attributes = True

@router.get("/policies", response_model=List[PolicySchema])
def get_policies(db: Session = Depends(get_db)):
    """
    Returns current routing policies.
    """
    result = db.execute(select(RoutingPolicy))
    policies = result.scalars().all()
    return policies

@router.put("/policies")
def update_policy(
    request: PolicyUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Updates confidence thresholds for a given domain.
    """
    result = db.execute(select(RoutingPolicy).where(RoutingPolicy.domain == request.domain))
    policy = result.scalars().first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy domain '{request.domain}' not found"
        )
        
    policy.min_confidence_threshold = round(request.min_confidence_threshold, 2)
    db.commit()
    
    return {
        "status": "success",
        "message": f"Updated {request.domain} confidence threshold successfully",
        "domain": request.domain,
        "new_threshold": policy.min_confidence_threshold
    }
