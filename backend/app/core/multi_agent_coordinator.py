from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.agents.base import BaseAgent
from backend.app.agents.cheap_agent import CheapAgent
from backend.app.agents.rag_agent import RAGAgent
from backend.app.agents.frontier_agent import FrontierAgent
from backend.app.agents.consensus_agent import ConsensusAgent
from backend.app.agents.coding_agent import CodingAgent
from backend.app.agents.research_agent import ResearchAgent
from backend.app.agents.analysis_agent import AnalysisAgent
from backend.app.core.config import settings

class MultiAgentCoordinator:
    """
    Coordinator service managing specialized domain agents, agent registry metadata,
    and multi-agent collaboration workflows.
    """

    def __init__(self, mock_mode: bool = False):
        self.specialized_agents = {
            "coding": CodingAgent(),
            "research": ResearchAgent(),
            "analysis": AnalysisAgent(),
            "general": CheapAgent(),
            "rag": RAGAgent(),
            "frontier": FrontierAgent(),
            "consensus": ConsensusAgent()
        }
        if mock_mode:
            for agent in self.specialized_agents.values():
                agent.mock_mode = True

    def get_agent_for_task(self, task_type: str, fallback_tier: int = 1) -> BaseAgent:
        """
        Returns specialized agent matching task category or fallback tier.
        """
        task_lower = (task_type or "general").lower()
        if task_lower in self.specialized_agents:
            return self.specialized_agents[task_lower]
        
        # Tier-based mapping fallback
        tier_map = {
            1: self.specialized_agents["general"],
            2: self.specialized_agents["rag"],
            3: self.specialized_agents["frontier"],
            4: self.specialized_agents["consensus"]
        }
        return tier_map.get(fallback_tier, self.specialized_agents["general"])

    def get_registry(self) -> List[Dict[str, Any]]:
        """
        Returns metadata registry of all active specialized agents in the system pool.
        """
        is_live = not settings.is_mock_mode
        registry = [
            {
                "id": "agent-cheap",
                "name": "Cheap Direct Agent",
                "tier": 1,
                "specialization": "general",
                "model_name": self.specialized_agents["general"].model,
                "description": "Fast, commodity model for simple Q&A, greetings, and basic facts.",
                "cost_tier": "Low ($0.0001 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            },
            {
                "id": "agent-rag",
                "name": "Augmented RAG Agent",
                "tier": 2,
                "specialization": "rag",
                "model_name": self.specialized_agents["rag"].model,
                "description": "Vector-retrieval agent for document Q&A and knowledge base citations.",
                "cost_tier": "Balanced ($0.0002 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            },
            {
                "id": "agent-analysis",
                "name": "Specialized Analysis Agent",
                "tier": 2,
                "specialization": "analysis",
                "model_name": self.specialized_agents["analysis"].model,
                "description": "Data analytics, log parsing, dataset statistics, and structured metrics.",
                "cost_tier": "Balanced ($0.0002 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            },
            {
                "id": "agent-coding",
                "name": "Specialized Coding Agent",
                "tier": 3,
                "specialization": "coding",
                "model_name": self.specialized_agents["coding"].model,
                "description": "Software synthesis, syntax validation, unit test writing, and refactoring.",
                "cost_tier": "High ($0.0008 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            },
            {
                "id": "agent-research",
                "name": "Specialized Research Agent",
                "tier": 3,
                "specialization": "research",
                "model_name": self.specialized_agents["research"].model,
                "description": "System design, security audits, technical trade-offs, and research reports.",
                "cost_tier": "High ($0.0008 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            },
            {
                "id": "agent-frontier",
                "name": "Frontier Reasoning Agent",
                "tier": 3,
                "specialization": "reasoning",
                "model_name": self.specialized_agents["frontier"].model,
                "description": "High-capacity frontier model for multi-step reasoning and complex tasks.",
                "cost_tier": "High ($0.0008 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            },
            {
                "id": "agent-consensus",
                "name": "Consensus & Verify Loop Agent",
                "tier": 4,
                "specialization": "consensus",
                "model_name": self.specialized_agents["consensus"].model,
                "description": "Multi-agent cross-verification and synthesis loop for high-stakes queries.",
                "cost_tier": "Premium ($0.0020 / 1k tokens)",
                "provider": "Groq",
                "status": "live" if is_live else "mock"
            }
        ]
        return registry

    async def execute_collaborative(
        self,
        prompt: str,
        primary_task: str,
        db: Optional[Session] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        expected_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes collaborative multi-agent workflow when a prompt spans multiple domains.
        """
        primary_agent = self.get_agent_for_task(primary_task)
        res_primary = await primary_agent.execute(prompt=prompt, messages=messages, expected_format=expected_format, db=db)
        
        # Add collaboration metadata flag
        res_primary["collaboration_flow"] = f"Specialized ({primary_agent.name})"
        return res_primary

multi_agent_coordinator = MultiAgentCoordinator()
