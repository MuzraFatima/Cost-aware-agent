from fastapi import APIRouter
from typing import Dict, Any, List

from backend.app.core.multi_agent_coordinator import multi_agent_coordinator

router = APIRouter()

@router.get("/registry")
def list_agent_registry():
    """
    Returns full metadata registry of all specialized agents in the CAAR multi-agent pool.
    """
    registry = multi_agent_coordinator.get_registry()
    return {
        "status": "success",
        "total_agents": len(registry),
        "agents": registry
    }
